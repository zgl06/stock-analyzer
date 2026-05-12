"""Phase F: build point-in-time feature rows keyed by `(ticker, as_of)`.

Input is typically the Phase E label output containing at least:

- `ticker`
- `as_of`

Output is a feature table with lagged price features plus best-effort
fundamental/analyst fields from free sources (yfinance).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd
import yfinance as yf

from backend.app.services.normalize import build_normalized_financials


@dataclass(frozen=True, slots=True)
class FeatureBuildReport:
    tickers_requested: int
    rows_requested: int
    existing_pairs: int
    rows_written_new: int
    rows_total: int
    date_min: date | None
    date_max: date | None
    null_rate_price_ret_12m: float
    null_rate_beta_spy_1y: float
    null_rate_revenue_yoy_growth: float
    null_rate_analyst_count: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class FeatureProvider(Protocol):
    def get_price_history(self, ticker: str) -> pd.Series:
        """Return adjusted daily close history (DatetimeIndex, ascending)."""

    def get_info(self, ticker: str) -> dict[str, object]:
        """Return provider info dict (market cap, PE, analyst fields)."""

    def get_normalized_financials(self, ticker: str) -> pd.DataFrame:
        """Return normalized annual periods as DataFrame with `period_end` and core fields."""


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


def _dataframe_to_records(frame: object) -> list[dict[str, object]]:
    """Convert yfinance statement DataFrame -> list[dict] shaped like market_data payload."""
    if frame is None:
        return []
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    # yfinance: rows=metrics, cols=period dates; convert to records keyed by date.
    out: list[dict[str, object]] = []
    for col in frame.columns:
        rec: dict[str, object] = {"index": pd.Timestamp(col).date().isoformat()}
        for metric in frame.index:
            rec[str(metric)] = frame.loc[metric, col]
        out.append(rec)
    return out


class YFinanceFeatureProvider:
    """Free-data feature provider with simple in-memory caches by ticker."""

    def __init__(self) -> None:
        self._price_cache: dict[str, pd.Series] = {}
        self._info_cache: dict[str, dict[str, object]] = {}
        self._fin_cache: dict[str, pd.DataFrame] = {}

    def _ticker(self, ticker: str) -> yf.Ticker:
        return yf.Ticker(ticker.strip().upper())

    def get_price_history(self, ticker: str) -> pd.Series:
        t = ticker.strip().upper()
        if t in self._price_cache:
            return self._price_cache[t]
        hist = self._ticker(t).history(period="max", interval="1d", auto_adjust=True)
        if hist is None or hist.empty or "Close" not in hist.columns:
            s = pd.Series(dtype=float)
        else:
            s = pd.Series(hist["Close"].dropna().astype(float))
            s = s.sort_index()
        self._price_cache[t] = s
        return s

    def get_info(self, ticker: str) -> dict[str, object]:
        t = ticker.strip().upper()
        if t in self._info_cache:
            return self._info_cache[t]
        info = self._ticker(t).info or {}
        self._info_cache[t] = dict(info)
        return self._info_cache[t]

    def get_normalized_financials(self, ticker: str) -> pd.DataFrame:
        t = ticker.strip().upper()
        if t in self._fin_cache:
            return self._fin_cache[t]

        y = self._ticker(t)
        payload = {
            "financials": {
                "income_stmt": _dataframe_to_records(getattr(y, "income_stmt", None)),
                "balance_sheet": _dataframe_to_records(getattr(y, "balance_sheet", None)),
                "cashflow": _dataframe_to_records(getattr(y, "cashflow", None)),
            }
        }
        nf = build_normalized_financials(payload)
        rows = []
        for p in nf.periods:
            rows.append(
                {
                    "period_end": p.period_end,
                    "revenue_yoy_growth": p.revenue_yoy_growth,
                    "net_income_yoy_growth": p.net_income_yoy_growth,
                    "gross_margin": p.gross_margin,
                    "operating_margin": p.operating_margin,
                    "revenue_usd": p.revenue_usd,
                    "free_cash_flow_usd": p.free_cash_flow_usd,
                    "total_debt_usd": p.total_debt_usd,
                    "cash_and_equivalents_usd": p.cash_and_equivalents_usd,
                }
            )
        df = pd.DataFrame(rows)
        if not df.empty:
            df["period_end"] = pd.to_datetime(df["period_end"]).dt.date
            df = df.sort_values("period_end")
        self._fin_cache[t] = df
        return df


def _ret_n(s: pd.Series, n_days: int) -> float | None:
    if len(s) <= n_days:
        return None
    p0 = _safe_float(s.iloc[-(n_days + 1)])
    p1 = _safe_float(s.iloc[-1])
    if p0 is None or p1 is None or p0 <= 0:
        return None
    return p1 / p0 - 1.0


def _beta_1y(stock_close: pd.Series, spy_close: pd.Series, as_of: date) -> float | None:
    s = stock_close[stock_close.index.date <= as_of].tail(253).pct_change().dropna()
    b = spy_close[spy_close.index.date <= as_of].tail(253).pct_change().dropna()
    if s.empty or b.empty:
        return None
    joined = pd.concat([s, b], axis=1, join="inner").dropna()
    if len(joined) < 30:
        return None
    rs = joined.iloc[:, 0]
    rb = joined.iloc[:, 1]
    var_b = float(rb.var())
    if var_b <= 0:
        return None
    cov = float(rs.cov(rb))
    return cov / var_b


def _fundamental_snapshot(fin_df: pd.DataFrame, as_of: date) -> dict[str, float | None]:
    if fin_df.empty:
        return {
            "revenue_yoy_growth": None,
            "net_income_yoy_growth": None,
            "gross_margin": None,
            "operating_margin": None,
            "debt_to_cash": None,
            "fcf_margin": None,
        }
    eligible = fin_df[fin_df["period_end"] <= as_of]
    if eligible.empty:
        return {
            "revenue_yoy_growth": None,
            "net_income_yoy_growth": None,
            "gross_margin": None,
            "operating_margin": None,
            "debt_to_cash": None,
            "fcf_margin": None,
        }
    r = eligible.iloc[-1]
    rev = _safe_float(r.get("revenue_usd"))
    fcf = _safe_float(r.get("free_cash_flow_usd"))
    debt = _safe_float(r.get("total_debt_usd"))
    cash = _safe_float(r.get("cash_and_equivalents_usd"))
    fcf_margin = (fcf / rev) if (fcf is not None and rev and rev != 0) else None
    debt_to_cash = (debt / cash) if (debt is not None and cash and cash > 0) else None
    return {
        "revenue_yoy_growth": _safe_float(r.get("revenue_yoy_growth")),
        "net_income_yoy_growth": _safe_float(r.get("net_income_yoy_growth")),
        "gross_margin": _safe_float(r.get("gross_margin")),
        "operating_margin": _safe_float(r.get("operating_margin")),
        "debt_to_cash": debt_to_cash,
        "fcf_margin": fcf_margin,
    }


def _build_features_for_row(
    ticker: str,
    as_of: date,
    *,
    stock_close: pd.Series,
    spy_close: pd.Series,
    info: dict[str, object],
    fin_df: pd.DataFrame,
) -> dict[str, object]:
    s = stock_close[stock_close.index.date <= as_of]
    last_close = _safe_float(s.iloc[-1]) if len(s) else None
    ret_1m = _ret_n(s, 21)
    ret_3m = _ret_n(s, 63)
    ret_6m = _ret_n(s, 126)
    ret_12m = _ret_n(s, 252)

    daily = s.tail(253).pct_change().dropna()
    vol_3m = float(daily.tail(63).std() * np.sqrt(252)) if len(daily) >= 20 else None
    if len(s.tail(252)) >= 20:
        win = s.tail(252)
        dd = win / win.cummax() - 1.0
        mdd_1y = float(dd.min())
    else:
        mdd_1y = None
    beta_1y = _beta_1y(stock_close, spy_close, as_of)

    f = _fundamental_snapshot(fin_df, as_of)

    return {
        "ticker": ticker,
        "as_of": as_of,
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
        "beta_spy_1y": beta_1y,
        "market_cap_usd": _safe_float(info.get("marketCap")),
        "trailing_pe": _safe_float(info.get("trailingPE")),
        "price_to_sales": _safe_float(info.get("priceToSalesTrailing12Months")),
        "analyst_count": _safe_float(info.get("numberOfAnalystOpinions")),
        "analyst_target_mean_price": _safe_float(info.get("targetMeanPrice")),
        "analyst_recommendation_mean": _safe_float(info.get("recommendationMean")),
        **f,
    }


def build_feature_dataset_from_labels(
    labels_df: pd.DataFrame,
    *,
    existing_features: pd.DataFrame | None = None,
    provider: FeatureProvider | None = None,
) -> tuple[pd.DataFrame, FeatureBuildReport]:
    """Build PIT feature rows from Phase E labels keys (`ticker`,`as_of`)."""
    if not {"ticker", "as_of"}.issubset(labels_df.columns):
        raise ValueError("labels_df must contain columns: ticker, as_of")
    if provider is None:
        provider = YFinanceFeatureProvider()

    src = labels_df.copy()
    src["ticker"] = src["ticker"].astype(str).str.upper().str.strip()
    src["as_of"] = pd.to_datetime(src["as_of"]).dt.date
    req = src[["ticker", "as_of"]].drop_duplicates().sort_values(["ticker", "as_of"])

    existing_df = existing_features.copy() if existing_features is not None else pd.DataFrame()
    existing_keys: set[tuple[str, date]] = set()
    if not existing_df.empty and {"ticker", "as_of"}.issubset(existing_df.columns):
        tmp = existing_df.copy()
        tmp["ticker"] = tmp["ticker"].astype(str).str.upper().str.strip()
        tmp["as_of"] = pd.to_datetime(tmp["as_of"]).dt.date
        existing_keys = {(r.ticker, r.as_of) for r in tmp.itertuples(index=False)}

    spy_close = provider.get_price_history("SPY")

    rows: list[dict[str, object]] = []
    for ticker, grp in req.groupby("ticker"):
        stock_close = provider.get_price_history(ticker)
        info = provider.get_info(ticker)
        fin_df = provider.get_normalized_financials(ticker)
        for as_of in grp["as_of"].tolist():
            if (ticker, as_of) in existing_keys:
                continue
            rows.append(
                _build_features_for_row(
                    ticker,
                    as_of,
                    stock_close=stock_close,
                    spy_close=spy_close,
                    info=info,
                    fin_df=fin_df,
                )
            )

    new_df = pd.DataFrame(rows)
    if existing_df.empty:
        all_df = new_df.copy()
    elif new_df.empty:
        all_df = existing_df.copy()
    else:
        all_df = pd.concat([existing_df, new_df], ignore_index=True)

    if not all_df.empty:
        all_df["ticker"] = all_df["ticker"].astype(str).str.upper().str.strip()
        all_df["as_of"] = pd.to_datetime(all_df["as_of"]).dt.date
        all_df = all_df.sort_values(["ticker", "as_of"]).drop_duplicates(
            subset=["ticker", "as_of"], keep="last"
        )
        all_df = all_df.reset_index(drop=True)

    def _null_rate(col: str) -> float:
        if all_df.empty or col not in all_df.columns:
            return 1.0
        return float(all_df[col].isna().mean())

    dmin: date | None = None
    dmax: date | None = None
    if not all_df.empty:
        dmin = min(all_df["as_of"])
        dmax = max(all_df["as_of"])

    report = FeatureBuildReport(
        tickers_requested=int(req["ticker"].nunique()),
        rows_requested=len(req),
        existing_pairs=len(existing_keys),
        rows_written_new=len(new_df),
        rows_total=len(all_df),
        date_min=dmin,
        date_max=dmax,
        null_rate_price_ret_12m=_null_rate("price_ret_12m"),
        null_rate_beta_spy_1y=_null_rate("beta_spy_1y"),
        null_rate_revenue_yoy_growth=_null_rate("revenue_yoy_growth"),
        null_rate_analyst_count=_null_rate("analyst_count"),
    )
    return all_df, report


def read_existing_feature_output(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, parse_dates=["as_of"], keep_default_na=True)
    if path.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported output extension: {path.suffix}. Use .csv or .parquet")


def write_feature_output(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".csv":
        df.to_csv(path, index=False)
        return
    if path.suffix.lower() in {".parquet", ".pq"}:
        df.to_parquet(path, index=False)
        return
    raise ValueError(f"Unsupported output extension: {path.suffix}. Use .csv or .parquet")

