"""Regression tests for normalize.build_normalized_financials.

yfinance returns annual statements newest-first, so if we don't sort the
periods ascending before computing YoY growth each period's "previous"
becomes the year that's actually one year *newer*, and every YoY comes
out negated. This test locks in the correct ordering and sign.
"""

from __future__ import annotations

import pytest

from backend.app.services.normalize import build_normalized_financials


def _income_record(date_iso: str, revenue: float, net_income: float) -> dict:
    return {
        "index": date_iso,
        "Total Revenue": revenue,
        "Net Income": net_income,
        "Gross Profit": revenue * 0.6,
        "Operating Income": revenue * 0.4,
    }


def _yfinance_payload_newest_first() -> dict:
    """Build a minimal yfinance-shaped payload with periods in newest-first order."""
    return {
        "financials": {
            "income_stmt": [
                _income_record("2025-06-30", 281_720_000_000, 101_830_000_000),
                _income_record("2024-06-30", 245_120_000_000, 88_140_000_000),
                _income_record("2023-06-30", 211_910_000_000, 72_360_000_000),
                _income_record("2022-06-30", 198_270_000_000, 72_740_000_000),
            ],
            "balance_sheet": [],
            "cashflow": [],
        }
    }


def test_periods_are_returned_oldest_first() -> None:
    financials = build_normalized_financials(_yfinance_payload_newest_first())

    period_ends = [str(p.period_end) for p in financials.periods]
    assert period_ends == [
        "2022-06-30",
        "2023-06-30",
        "2024-06-30",
        "2025-06-30",
    ]


def test_revenue_yoy_growth_is_positive_for_growing_company() -> None:
    financials = build_normalized_financials(_yfinance_payload_newest_first())
    periods = financials.periods

    # Oldest period never has a "previous" to compare against.
    assert periods[0].revenue_yoy_growth is None

    # +18% from 198B to 212B
    assert periods[1].revenue_yoy_growth == pytest.approx(
        (211.91 - 198.27) / 198.27, abs=1e-3
    )
    # +15.7% from 212B to 245B
    assert periods[2].revenue_yoy_growth == pytest.approx(
        (245.12 - 211.91) / 211.91, abs=1e-3
    )
    # +14.9% from 245B to 282B
    assert periods[3].revenue_yoy_growth == pytest.approx(
        (281.72 - 245.12) / 245.12, abs=1e-3
    )

    # All positive, as expected for a growing company.
    assert all(
        p.revenue_yoy_growth > 0
        for p in periods
        if p.revenue_yoy_growth is not None
    )


def test_latest_period_is_labeled_ttm() -> None:
    financials = build_normalized_financials(_yfinance_payload_newest_first())

    # Only the newest (last in ascending order) period should be TTM.
    assert financials.periods[-1].fiscal_period == "TTM"
    for period in financials.periods[:-1]:
        assert period.fiscal_period == "FY"

    assert financials.latest_fiscal_year == 2025
    assert financials.latest_fiscal_period == "TTM"
