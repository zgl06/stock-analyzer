"""Tests for analysis.feature_dataset (Phase F)."""

from __future__ import annotations

from datetime import date

import pandas as pd

from backend.app.analysis.feature_dataset import build_feature_dataset_from_labels


class _FakeProvider:
    def __init__(self) -> None:
        idx = pd.date_range(start="2019-01-01", periods=800, freq="B")
        # Upward trend for deterministic positive returns.
        self._stock = pd.Series([100.0 + i * 0.2 for i in range(len(idx))], index=idx)
        self._spy = pd.Series([200.0 + i * 0.1 for i in range(len(idx))], index=idx)

    def get_price_history(self, ticker: str) -> pd.Series:
        t = ticker.upper()
        if t == "SPY":
            return self._spy
        return self._stock

    def get_info(self, ticker: str) -> dict[str, object]:
        return {
            "marketCap": 1_000_000_000,
            "trailingPE": 22.5,
            "priceToSalesTrailing12Months": 5.3,
            "numberOfAnalystOpinions": 33,
            "targetMeanPrice": 210.5,
            "recommendationMean": 2.1,
        }

    def get_normalized_financials(self, ticker: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "period_end": date(2021, 12, 31),
                    "revenue_yoy_growth": 0.12,
                    "net_income_yoy_growth": 0.15,
                    "gross_margin": 0.55,
                    "operating_margin": 0.31,
                    "revenue_usd": 100.0,
                    "free_cash_flow_usd": 20.0,
                    "total_debt_usd": 50.0,
                    "cash_and_equivalents_usd": 25.0,
                },
                {
                    "period_end": date(2022, 12, 31),
                    "revenue_yoy_growth": 0.10,
                    "net_income_yoy_growth": 0.09,
                    "gross_margin": 0.53,
                    "operating_margin": 0.29,
                    "revenue_usd": 120.0,
                    "free_cash_flow_usd": 18.0,
                    "total_debt_usd": 48.0,
                    "cash_and_equivalents_usd": 24.0,
                },
            ]
        )


def test_build_feature_dataset_from_labels_basic() -> None:
    labels = pd.DataFrame(
        [
            {"ticker": "AAPL", "as_of": date(2023, 1, 3)},
            {"ticker": "AAPL", "as_of": date(2023, 2, 1)},
            {"ticker": "MSFT", "as_of": date(2023, 1, 3)},
        ]
    )
    out, report = build_feature_dataset_from_labels(labels, provider=_FakeProvider())
    assert len(out) == 3
    assert report.rows_requested == 3
    assert report.rows_total == 3
    assert {"price_ret_12m", "beta_spy_1y", "revenue_yoy_growth", "analyst_count"}.issubset(
        out.columns
    )
    # Deterministic fake data should produce non-null core features.
    assert out["price_ret_12m"].notna().all()
    assert out["analyst_count"].notna().all()
    assert out["revenue_yoy_growth"].notna().all()


def test_resume_skips_existing_pairs() -> None:
    labels = pd.DataFrame(
        [
            {"ticker": "AAPL", "as_of": date(2023, 1, 3)},
            {"ticker": "AAPL", "as_of": date(2023, 2, 1)},
        ]
    )
    existing = pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "as_of": date(2023, 1, 3),
                "price_ret_12m": 0.1,
            }
        ]
    )
    out, report = build_feature_dataset_from_labels(
        labels,
        existing_features=existing,
        provider=_FakeProvider(),
    )
    assert report.existing_pairs == 1
    assert report.rows_written_new == 1
    assert report.rows_total == 2
    assert len(out) == 2

