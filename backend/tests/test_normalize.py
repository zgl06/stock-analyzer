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


def _quarter_income_record(
    date_iso: str,
    revenue: float,
    net_income: float,
    *,
    shares: float = 100.0,
) -> dict:
    return {
        "index": date_iso,
        "Total Revenue": revenue,
        "Net Income": net_income,
        "Gross Profit": revenue * 0.6,
        "Operating Income": revenue * 0.4,
        "Diluted EPS": net_income / shares,
        "Diluted Average Shares": shares,
    }


def _quarter_cashflow_record(date_iso: str, operating: float, capex: float) -> dict:
    return {
        "index": date_iso,
        "Operating Cash Flow": operating,
        "Capital Expenditure": capex,
    }


def _quarter_balance_record(date_iso: str, cash: float, debt: float) -> dict:
    return {
        "index": date_iso,
        "Cash And Cash Equivalents": cash,
        "Total Debt": debt,
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


def _yfinance_payload_with_quarters() -> dict:
    payload = _yfinance_payload_newest_first()
    payload["financials"].update(
        {
            "quarterly_income_stmt": [
                _quarter_income_record("2025-09-30", 78.0, 15.6),
                _quarter_income_record("2025-06-30", 74.0, 14.8),
                _quarter_income_record("2025-03-31", 72.0, 14.4),
                _quarter_income_record("2024-12-31", 70.0, 14.0),
            ],
            "quarterly_cashflow": [
                _quarter_cashflow_record("2025-09-30", 20.0, -4.0),
                _quarter_cashflow_record("2025-06-30", 19.0, -4.0),
                _quarter_cashflow_record("2025-03-31", 18.0, -3.0),
                _quarter_cashflow_record("2024-12-31", 17.0, -3.0),
            ],
            "quarterly_balance_sheet": [
                _quarter_balance_record("2025-09-30", 35.0, 82.0),
                _quarter_balance_record("2025-06-30", 33.0, 80.0),
            ],
        }
    )
    return payload


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


def test_builds_ttm_period_from_latest_four_quarters_when_available() -> None:
    financials = build_normalized_financials(_yfinance_payload_with_quarters())
    latest = financials.periods[-1]

    assert latest.fiscal_period == "TTM"
    assert str(latest.period_end) == "2025-09-30"
    assert latest.revenue_usd == pytest.approx(294.0)
    assert latest.net_income_usd == pytest.approx(58.8)
    assert latest.free_cash_flow_usd == pytest.approx(60.0)
    assert latest.cash_and_equivalents_usd == pytest.approx(35.0)
    assert latest.total_debt_usd == pytest.approx(82.0)
    assert latest.gross_margin == pytest.approx(0.6)
    assert latest.operating_margin == pytest.approx(0.4)
    assert latest.diluted_eps == pytest.approx(0.588)


def test_falls_back_to_latest_annual_as_ttm_when_quarter_data_is_incomplete() -> None:
    payload = _yfinance_payload_with_quarters()
    payload["financials"]["quarterly_income_stmt"] = payload["financials"][
        "quarterly_income_stmt"
    ][:3]

    financials = build_normalized_financials(payload)

    assert financials.periods[-1].fiscal_period == "TTM"
    assert str(financials.periods[-1].period_end) == "2025-06-30"
    assert len(financials.periods) == 4


def test_skips_obviously_empty_annual_periods() -> None:
    payload = {
        "financials": {
            "income_stmt": [
                {
                    "index": "2025-06-30",
                    "Diluted EPS": 1.5,
                },
                _income_record("2024-06-30", 245.0, 88.0),
            ],
            "balance_sheet": [],
            "cashflow": [],
        }
    }

    financials = build_normalized_financials(payload)

    assert len(financials.periods) == 1
    assert str(financials.periods[0].period_end) == "2024-06-30"
    assert financials.periods[0].fiscal_period == "TTM"


def test_periods_remain_sorted_with_only_one_ttm() -> None:
    financials = build_normalized_financials(_yfinance_payload_with_quarters())

    period_ends = [period.period_end for period in financials.periods]
    assert period_ends == sorted(period_ends)
    assert sum(period.fiscal_period == "TTM" for period in financials.periods) == 1
