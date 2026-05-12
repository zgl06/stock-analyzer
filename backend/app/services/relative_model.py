from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import Booster

from backend.app.analysis.benchmarks import BROAD_BENCHMARK_TICKER, sector_etf_ticker
from backend.app.analysis.feature_dataset import YFinanceFeatureProvider
from backend.app.config import Settings
from backend.app.models.analysis_output import RelativePerformanceView, RelativeTercileEstimate


_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_SPY_MODEL_PATH = _REPO_ROOT / "backend" / "outputs" / "models" / "lgbm_excess_spy.txt"
_DEFAULT_SPY_FEATURES_PATH = (
    _REPO_ROOT / "backend" / "outputs" / "reports" / "lgbm_excess_spy_features.json"
)
_DEFAULT_SPY_PREDS_PATH = (
    _REPO_ROOT / "backend" / "outputs" / "reports" / "lgbm_excess_spy_test_preds.csv"
)
_DEFAULT_SECTOR_MODEL_PATH = (
    _REPO_ROOT / "backend" / "outputs" / "models" / "lgbm_excess_sector.txt"
)
_DEFAULT_SECTOR_FEATURES_PATH = (
    _REPO_ROOT / "backend" / "outputs" / "reports" / "lgbm_excess_sector_features.json"
)
_DEFAULT_SECTOR_PREDS_PATH = (
    _REPO_ROOT / "backend" / "outputs" / "reports" / "lgbm_excess_sector_test_preds.csv"
)


def _safe_float(v: object) -> float | None:
    try:
        if v is None:
            return None
        x = float(v)
        if np.isnan(x):
            return None
        return x
    except Exception:
        return None


@dataclass(slots=True)
class _ModelBundle:
    name: str
    model_path: Path
    feature_names_path: Path
    preds_path: Path
    model: Booster | None = None
    feature_names: list[str] | None = None
    score_min: float | None = None
    score_max: float | None = None

    def load(self) -> None:
        if self.model is None:
            if not self.model_path.exists():
                raise FileNotFoundError(f"{self.name} model not found: {self.model_path}")
            self.model = Booster(model_file=str(self.model_path))
        if self.feature_names is None:
            if not self.feature_names_path.exists():
                raise FileNotFoundError(
                    f"{self.name} feature names not found: {self.feature_names_path}"
                )
            payload = json.loads(self.feature_names_path.read_text(encoding="utf-8"))
            cols = payload.get("feature_columns", [])
            if not isinstance(cols, list) or not cols:
                raise ValueError(f"{self.name} feature names file has no feature_columns")
            self.feature_names = [str(c) for c in cols]
        if self.score_min is None or self.score_max is None:
            if self.preds_path.exists():
                try:
                    p = pd.read_csv(self.preds_path)
                    if "y_pred" in p.columns and not p["y_pred"].dropna().empty:
                        self.score_min = float(p["y_pred"].min())
                        self.score_max = float(p["y_pred"].max())
                except Exception:
                    self.score_min = None
                    self.score_max = None

    def predict(self, row: dict[str, float | None]) -> tuple[float, float, int, str]:
        self.load()
        assert self.model is not None
        assert self.feature_names is not None
        x = pd.DataFrame([{c: row.get(c) for c in self.feature_names}])
        # LightGBM requires numeric dtypes; yfinance / mixed None types can leave object columns.
        x = x.apply(pd.to_numeric, errors="coerce").astype("float64")
        raw = float(self.model.predict(x)[0])
        if (
            self.score_min is not None
            and self.score_max is not None
            and self.score_max > self.score_min
        ):
            score01 = float(np.clip((raw - self.score_min) / (self.score_max - self.score_min), 0.0, 1.0))
        else:
            score01 = float(1.0 / (1.0 + np.exp(-raw)))
        tercile = 1 if score01 < (1 / 3) else 2 if score01 < (2 / 3) else 3
        available = sum(1 for c in self.feature_names if row.get(c) is not None)
        detail = f"features available={available}/{len(self.feature_names)}; raw_score={raw:.4f}"
        return raw, score01, tercile, detail


class RelativeModelService:
    """Loads and serves both vs-SPY and vs-sector model views."""

    def __init__(
        self,
        *,
        spy_model_path: Path | None = None,
        spy_features_path: Path | None = None,
        spy_preds_path: Path | None = None,
        sector_model_path: Path | None = None,
        sector_features_path: Path | None = None,
        sector_preds_path: Path | None = None,
    ) -> None:
        self.provider = YFinanceFeatureProvider()
        self.spy_bundle = _ModelBundle(
            name="spy",
            model_path=spy_model_path or _DEFAULT_SPY_MODEL_PATH,
            feature_names_path=spy_features_path or _DEFAULT_SPY_FEATURES_PATH,
            preds_path=spy_preds_path or _DEFAULT_SPY_PREDS_PATH,
        )
        self.sector_bundle = _ModelBundle(
            name="sector",
            model_path=sector_model_path or _DEFAULT_SECTOR_MODEL_PATH,
            feature_names_path=sector_features_path or _DEFAULT_SECTOR_FEATURES_PATH,
            preds_path=sector_preds_path or _DEFAULT_SECTOR_PREDS_PATH,
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> "RelativeModelService":
        def _resolve_path(value: str | None, default: Path) -> Path:
            if not value:
                return default
            p = Path(value)
            if p.is_absolute():
                return p
            return _REPO_ROOT / p

        return cls(
            spy_model_path=_resolve_path(settings.relative_model_path, _DEFAULT_SPY_MODEL_PATH),
            spy_features_path=_resolve_path(
                settings.relative_model_features_path, _DEFAULT_SPY_FEATURES_PATH
            ),
            spy_preds_path=_resolve_path(
                settings.relative_model_predictions_path, _DEFAULT_SPY_PREDS_PATH
            ),
            sector_model_path=_resolve_path(
                settings.relative_model_sector_path, _DEFAULT_SECTOR_MODEL_PATH
            ),
            sector_features_path=_resolve_path(
                settings.relative_model_sector_features_path, _DEFAULT_SECTOR_FEATURES_PATH
            ),
            sector_preds_path=_resolve_path(
                settings.relative_model_sector_predictions_path, _DEFAULT_SECTOR_PREDS_PATH
            ),
        )

    def _build_feature_row(self, ticker: str, as_of: date) -> dict[str, float | None]:
        t = ticker.strip().upper()
        stock_close = self.provider.get_price_history(t)
        spy_close = self.provider.get_price_history("SPY")
        info = self.provider.get_info(t)
        fin_df = self.provider.get_normalized_financials(t)

        # Reuse logic from Phase F by computing same fields inline.
        s = stock_close[stock_close.index.date <= as_of]
        last_close = _safe_float(s.iloc[-1]) if len(s) else None

        def _ret_n(n: int) -> float | None:
            if len(s) <= n:
                return None
            p0 = _safe_float(s.iloc[-(n + 1)])
            p1 = _safe_float(s.iloc[-1])
            if p0 is None or p1 is None or p0 <= 0:
                return None
            return p1 / p0 - 1.0

        ret_1m = _ret_n(21)
        ret_3m = _ret_n(63)
        ret_6m = _ret_n(126)
        ret_12m = _ret_n(252)
        daily = s.tail(253).pct_change().dropna()
        vol_3m = float(daily.tail(63).std() * np.sqrt(252)) if len(daily) >= 20 else None
        if len(s.tail(252)) >= 20:
            win = s.tail(252)
            dd = win / win.cummax() - 1.0
            mdd_1y = float(dd.min())
        else:
            mdd_1y = None

        rs = s.tail(253).pct_change().dropna()
        rb = spy_close[spy_close.index.date <= as_of].tail(253).pct_change().dropna()
        joined = pd.concat([rs, rb], axis=1, join="inner").dropna()
        beta = None
        if len(joined) >= 30:
            var_b = float(joined.iloc[:, 1].var())
            if var_b > 0:
                beta = float(joined.iloc[:, 0].cov(joined.iloc[:, 1]) / var_b)

        f = {
            "revenue_yoy_growth": None,
            "net_income_yoy_growth": None,
            "gross_margin": None,
            "operating_margin": None,
            "debt_to_cash": None,
            "fcf_margin": None,
        }
        if not fin_df.empty:
            eligible = fin_df[fin_df["period_end"] <= as_of]
            if not eligible.empty:
                r = eligible.iloc[-1]
                rev = _safe_float(r.get("revenue_usd"))
                fcf = _safe_float(r.get("free_cash_flow_usd"))
                debt = _safe_float(r.get("total_debt_usd"))
                cash = _safe_float(r.get("cash_and_equivalents_usd"))
                f = {
                    "revenue_yoy_growth": _safe_float(r.get("revenue_yoy_growth")),
                    "net_income_yoy_growth": _safe_float(r.get("net_income_yoy_growth")),
                    "gross_margin": _safe_float(r.get("gross_margin")),
                    "operating_margin": _safe_float(r.get("operating_margin")),
                    "debt_to_cash": (debt / cash) if (debt is not None and cash and cash > 0) else None,
                    "fcf_margin": (fcf / rev) if (fcf is not None and rev and rev != 0) else None,
                }

        row: dict[str, float | None] = {
            "price_close": last_close,
            "price_ret_1m": ret_1m,
            "price_ret_3m": ret_3m,
            "price_ret_6m": ret_6m,
            "price_ret_12m": ret_12m,
            "price_momentum_12m_minus_1m": (
                (ret_12m - ret_1m) if ret_12m is not None and ret_1m is not None else None
            ),
            "volatility_3m_ann": vol_3m,
            "max_drawdown_1y": mdd_1y,
            "beta_spy_1y": beta,
            "market_cap_usd": _safe_float(info.get("marketCap")),
            "trailing_pe": _safe_float(info.get("trailingPE")),
            "price_to_sales": _safe_float(info.get("priceToSalesTrailing12Months")),
            "analyst_count": _safe_float(info.get("numberOfAnalystOpinions")),
            "analyst_target_mean_price": _safe_float(info.get("targetMeanPrice")),
            "analyst_recommendation_mean": _safe_float(info.get("recommendationMean")),
            **f,
        }
        return row

    def get_relative_view(self, *, ticker: str, sector: str | None = None) -> RelativePerformanceView:
        t = ticker.strip().upper()
        as_of = date.today()
        row = self._build_feature_row(t, as_of)

        mapped_sector_etf = sector_etf_ticker(sector or "") if sector else None
        try:
            _, spy_score, spy_tercile, spy_detail = self.spy_bundle.predict(row)
            spy_est = RelativeTercileEstimate(
                benchmark_ticker=BROAD_BENCHMARK_TICKER,
                tercile=spy_tercile,
                score=spy_score,
                methodology="lightgbm",
                detail=spy_detail,
            )
        except Exception as error:
            spy_est = RelativeTercileEstimate(
                benchmark_ticker=BROAD_BENCHMARK_TICKER,
                tercile=None,
                score=None,
                methodology="unavailable",
                detail=f"SPY model unavailable: {error}",
            )

        if mapped_sector_etf:
            try:
                _, sec_score, sec_tercile, sec_detail = self.sector_bundle.predict(row)
                sec_est = RelativeTercileEstimate(
                    benchmark_ticker=mapped_sector_etf,
                    tercile=sec_tercile,
                    score=sec_score,
                    methodology="lightgbm",
                    detail=sec_detail,
                )
            except Exception as error:
                sec_est = RelativeTercileEstimate(
                    benchmark_ticker=mapped_sector_etf,
                    tercile=None,
                    score=None,
                    methodology="unavailable",
                    detail=f"Sector model unavailable: {error}",
                )
        else:
            sec_est = RelativeTercileEstimate(
                benchmark_ticker="UNKNOWN",
                tercile=None,
                score=None,
                methodology="unavailable",
                detail="Sector ETF mapping unavailable for ticker sector.",
            )

        return RelativePerformanceView(
            horizon_years=5,
            as_of=as_of.isoformat(),
            gics_sector=sector,
            sector_etf=mapped_sector_etf,
            used_parent_etf=False,
            vs_spy=spy_est,
            vs_sector=sec_est,
            feature_vector_version="v1",
            llm_commentary=None,
        )

