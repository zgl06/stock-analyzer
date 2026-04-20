"""Day 3 verification for the deterministic forecast engine."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from backend.app.analysis.forecast import (
    EXPECTED_RETURN_BOUNDS,
    HORIZON_YEARS,
    METHODOLOGY_VERSION,
    OPERATING_MARGIN_BOUNDS,
    REVENUE_CAGR_BOUNDS,
    SCENARIO_ORDER,
    TERMINAL_MULTIPLE_BOUNDS,
    build_forecast,
)
from backend.app.models import (
    AnalysisInput,
    CompanySnapshot,
    FinancialPeriod,
    MarketDataSnapshot,
    NormalizedFinancials,
)
from backend.app.services.fixture_loader import load_analysis_input_fixture


def _make_minimal_analysis_input(
    *,
    periods: list[FinancialPeriod] | None = None,
    market_data: MarketDataSnapshot | None = None,
) -> AnalysisInput:
    company = CompanySnapshot(
        ticker="TEST",
        company_name="Test Co.",
        cik="0000000001",
    )
    financials = NormalizedFinancials(
        latest_fiscal_year=2024,
        latest_fiscal_period="TTM",
        periods=periods or [],
    )
    market = market_data or MarketDataSnapshot(
        as_of=datetime(2024, 1, 1, tzinfo=timezone.utc),
        price_usd=100.0,
    )
    return AnalysisInput(
        company=company,
        financials=financials,
        filings=[],
        market_data=market,
    )


def _healthy_period(**overrides: object) -> FinancialPeriod:
    base = dict(
        period_end=date(2024, 12, 31),
        fiscal_year=2024,
        fiscal_period="TTM",
        revenue_usd=400_000_000_000.0,
        net_income_usd=100_000_000_000.0,
        gross_margin=0.45,
        operating_margin=0.30,
        free_cash_flow_usd=95_000_000_000.0,
        cash_and_equivalents_usd=60_000_000_000.0,
        total_debt_usd=110_000_000_000.0,
        shares_outstanding=15_000_000_000.0,
        revenue_yoy_growth=0.06,
        net_income_yoy_growth=0.08,
    )
    base.update(overrides)
    return FinancialPeriod(**base)  # type: ignore[arg-type]


def _healthy_market(**overrides: object) -> MarketDataSnapshot:
    base = dict(
        as_of=datetime(2025, 1, 1, tzinfo=timezone.utc),
        price_usd=200.0,
        market_cap_usd=3_000_000_000_000.0,
        price_to_earnings=28.0,
        price_to_sales=7.5,
    )
    base.update(overrides)
    return MarketDataSnapshot(**base)  # type: ignore[arg-type]


def test_methodology_version_is_scenarios_v1() -> None:
    assert METHODOLOGY_VERSION == "scenarios-v1"


def test_horizon_years_in_three_to_five_range() -> None:
    assert 3 <= HORIZON_YEARS <= 5


def test_scenario_order_is_bear_base_bull() -> None:
    assert SCENARIO_ORDER == ("bear", "base", "bull")


def test_forecast_returns_three_scenarios_in_order() -> None:
    analysis_input = load_analysis_input_fixture("AAPL")
    scenarios = build_forecast(analysis_input)

    assert len(scenarios) == 3
    assert tuple(s.scenario for s in scenarios) == SCENARIO_ORDER
    assert all(s.horizon_years == HORIZON_YEARS for s in scenarios)


def test_forecast_is_deterministic_for_same_input() -> None:
    analysis_input = load_analysis_input_fixture("AAPL")
    first = build_forecast(analysis_input)
    second = build_forecast(analysis_input)

    for a, b in zip(first, second):
        assert a.scenario == b.scenario
        assert a.revenue_cagr == b.revenue_cagr
        assert a.operating_margin_end == b.operating_margin_end
        assert a.terminal_multiple == b.terminal_multiple
        assert a.expected_annualized_return == b.expected_annualized_return


def test_bear_base_bull_strictly_ordered_for_aapl_fixture() -> None:
    bear, base, bull = build_forecast(load_analysis_input_fixture("AAPL"))

    assert bear.revenue_cagr < base.revenue_cagr < bull.revenue_cagr
    assert bear.operating_margin_end < base.operating_margin_end < bull.operating_margin_end
    assert bear.terminal_multiple < base.terminal_multiple < bull.terminal_multiple
    assert (
        bear.expected_annualized_return
        is not None
        and base.expected_annualized_return is not None
        and bull.expected_annualized_return is not None
    )
    assert (
        bear.expected_annualized_return
        <= base.expected_annualized_return
        <= bull.expected_annualized_return
    )


def test_forecast_values_within_declared_bounds() -> None:
    scenarios = build_forecast(load_analysis_input_fixture("AAPL"))

    for s in scenarios:
        assert s.revenue_cagr is not None
        assert REVENUE_CAGR_BOUNDS[0] <= s.revenue_cagr <= REVENUE_CAGR_BOUNDS[1]

        assert s.operating_margin_end is not None
        assert (
            OPERATING_MARGIN_BOUNDS[0]
            <= s.operating_margin_end
            <= OPERATING_MARGIN_BOUNDS[1]
        )

        assert s.terminal_multiple is not None
        assert (
            TERMINAL_MULTIPLE_BOUNDS[0]
            <= s.terminal_multiple
            <= TERMINAL_MULTIPLE_BOUNDS[1]
        )

        assert s.expected_annualized_return is not None
        assert (
            EXPECTED_RETURN_BOUNDS[0]
            <= s.expected_annualized_return
            <= EXPECTED_RETURN_BOUNDS[1]
        )

        assert s.assumptions is not None and s.assumptions != ""


def test_forecast_returns_assumptions_without_market_cap() -> None:
    analysis_input = _make_minimal_analysis_input(
        periods=[_healthy_period()],
        market_data=MarketDataSnapshot(
            as_of=datetime(2025, 1, 1, tzinfo=timezone.utc),
            price_usd=0.0,
        ),
    )

    scenarios = build_forecast(analysis_input)

    assert len(scenarios) == 3
    assert all(s.expected_annualized_return is None for s in scenarios)
    assert all(s.revenue_cagr is not None for s in scenarios)
    assert all(s.operating_margin_end is not None for s in scenarios)
    assert all(s.terminal_multiple is not None for s in scenarios)


def test_forecast_uses_default_growth_when_history_missing() -> None:
    period = _healthy_period(revenue_yoy_growth=None, net_income_yoy_growth=None)

    scenarios = build_forecast(
        _make_minimal_analysis_input(periods=[period], market_data=_healthy_market())
    )
    base = next(s for s in scenarios if s.scenario == "base")

    assert base.revenue_cagr == pytest.approx(0.05, abs=1e-9)


def test_forecast_falls_back_to_price_times_shares_for_market_cap() -> None:
    period = _healthy_period()
    market = _healthy_market(market_cap_usd=None)

    scenarios = build_forecast(
        _make_minimal_analysis_input(periods=[period], market_data=market)
    )

    assert all(s.expected_annualized_return is not None for s in scenarios)


def test_forecast_handles_completely_empty_input() -> None:
    scenarios = build_forecast(_make_minimal_analysis_input())

    assert len(scenarios) == 3
    assert tuple(s.scenario for s in scenarios) == SCENARIO_ORDER
    for s in scenarios:
        assert s.revenue_cagr is not None
        assert s.operating_margin_end is not None
        assert s.terminal_multiple is not None
        assert s.expected_annualized_return is None
        assert s.assumptions is not None


def test_extreme_growth_history_is_clamped_into_bounds() -> None:
    huge_growth_period = _healthy_period(revenue_yoy_growth=2.0)

    scenarios = build_forecast(
        _make_minimal_analysis_input(
            periods=[huge_growth_period], market_data=_healthy_market()
        )
    )

    for s in scenarios:
        assert s.revenue_cagr is not None
        assert s.revenue_cagr <= REVENUE_CAGR_BOUNDS[1]
