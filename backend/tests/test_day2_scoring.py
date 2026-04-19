"""Day 2 verification for the deterministic scoring engine."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from backend.app.analysis.scoring import (
    METHODOLOGY_VERSION,
    PILLAR_ORDER,
    PILLAR_WEIGHTS,
    score_company,
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


def test_pillar_weights_sum_to_one() -> None:
    assert pytest.approx(sum(PILLAR_WEIGHTS.values()), abs=1e-9) == 1.0


def test_pillar_order_matches_weights_keys() -> None:
    assert set(PILLAR_ORDER) == set(PILLAR_WEIGHTS.keys())


def test_methodology_version_is_deterministic_v1() -> None:
    assert METHODOLOGY_VERSION == "deterministic-v1"


def test_scoring_is_deterministic_for_same_input() -> None:
    analysis_input = load_analysis_input_fixture("AAPL")
    first = score_company(analysis_input)
    second = score_company(analysis_input)

    assert first.composite_score == second.composite_score
    assert first.methodology_version == second.methodology_version
    assert [p.score for p in first.pillars] == [p.score for p in second.pillars]
    assert [p.weight for p in first.pillars] == [p.weight for p in second.pillars]


def test_scoring_pillars_in_expected_order() -> None:
    analysis_input = load_analysis_input_fixture("AAPL")
    breakdown = score_company(analysis_input)

    pillar_names = tuple(p.pillar for p in breakdown.pillars)
    assert pillar_names == PILLAR_ORDER


def test_scoring_bounds_for_aapl_fixture() -> None:
    analysis_input = load_analysis_input_fixture("AAPL")
    breakdown = score_company(analysis_input)

    assert 0.0 <= breakdown.composite_score <= 1.0
    for pillar in breakdown.pillars:
        assert 0.0 <= pillar.score <= 1.0
        assert 0.0 <= pillar.weight <= 1.0
        assert pillar.rationale is not None and pillar.rationale != ""


def test_scoring_handles_missing_data_with_neutral_default() -> None:
    breakdown = score_company(_make_minimal_analysis_input())

    assert breakdown.composite_score == pytest.approx(0.5, abs=1e-9)
    assert all(p.score == pytest.approx(0.5, abs=1e-9) for p in breakdown.pillars)
    assert all(p.rationale and "neutral" in p.rationale.lower() for p in breakdown.pillars)


def test_scoring_uses_partial_data_when_available() -> None:
    period = FinancialPeriod(
        period_end=date(2024, 12, 31),
        fiscal_year=2024,
        fiscal_period="TTM",
        revenue_usd=100.0,
        net_income_usd=20.0,
        gross_margin=0.50,
        operating_margin=0.25,
        free_cash_flow_usd=15.0,
        cash_and_equivalents_usd=50.0,
        total_debt_usd=10.0,
        revenue_yoy_growth=0.10,
        net_income_yoy_growth=0.12,
    )
    market = MarketDataSnapshot(
        as_of=datetime(2024, 12, 31, tzinfo=timezone.utc),
        price_usd=50.0,
        price_to_earnings=15.0,
        price_to_sales=3.0,
    )

    breakdown = score_company(
        _make_minimal_analysis_input(periods=[period], market_data=market)
    )

    pillar_scores = {p.pillar: p.score for p in breakdown.pillars}

    assert pillar_scores["business_quality"] > 0.5
    assert pillar_scores["growth"] > 0.4
    assert pillar_scores["profitability"] > 0.5
    assert pillar_scores["balance_sheet"] > 0.5
    assert pillar_scores["valuation"] > 0.5
    assert breakdown.composite_score > 0.5


def test_composite_equals_weighted_sum_of_pillars() -> None:
    analysis_input = load_analysis_input_fixture("AAPL")
    breakdown = score_company(analysis_input)

    expected = sum(p.score * p.weight for p in breakdown.pillars)
    assert breakdown.composite_score == pytest.approx(expected, abs=1e-4)
