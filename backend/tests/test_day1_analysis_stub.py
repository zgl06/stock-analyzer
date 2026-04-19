"""Day 1 verification for the fixture-backed analysis stub."""

from __future__ import annotations

import pytest

from backend.app.analysis import (
    run_analysis_from_fixture,
    run_analysis_pipeline,
)
from backend.app.errors import NotFoundError
from backend.app.models import AnalysisInput, AnalysisResponse
from backend.app.services.fixture_loader import (
    available_fixture_tickers,
    load_analysis_input_fixture,
)


def test_fixture_loader_parses_aapl_as_analysis_input() -> None:
    analysis_input = load_analysis_input_fixture("AAPL")

    assert isinstance(analysis_input, AnalysisInput)
    assert analysis_input.company.ticker == "AAPL"
    assert analysis_input.company.cik == "0000320193"
    assert analysis_input.financials.periods, "fixture should include financial periods"
    assert analysis_input.market_data.price_usd > 0
    assert analysis_input.filings, "fixture should include filing records"


def test_fixture_loader_accepts_lowercase_ticker() -> None:
    assert load_analysis_input_fixture("aapl") is load_analysis_input_fixture("AAPL")


def test_fixture_loader_lists_available_tickers() -> None:
    assert "AAPL" in available_fixture_tickers()


def test_fixture_loader_raises_for_missing_ticker() -> None:
    with pytest.raises(NotFoundError):
        load_analysis_input_fixture("ZZZZ")


def test_pipeline_assembles_full_response_from_fixture() -> None:
    response = run_analysis_from_fixture("AAPL")

    assert isinstance(response, AnalysisResponse)
    assert response.ticker == "AAPL"
    assert response.source == "fixture"
    assert response.company.ticker == "AAPL"

    assert 0.0 <= response.score.composite_score <= 1.0
    assert response.score.pillars, "score breakdown should include pillar contributions"

    scenarios = {s.scenario for s in response.forecast}
    assert scenarios == {"bear", "base", "bull"}

    assert response.peers, "stub peer list should be non-empty"
    assert all(peer.ticker.upper() != "AAPL" for peer in response.peers), (
        "input company should never appear as its own peer"
    )

    assert response.verdict.rating in {"Strong Buy", "Buy", "Hold", "Avoid"}
    assert 0.0 <= response.verdict.confidence <= 1.0

    assert response.document_summary is not None
    assert response.document_summary.available is True


def test_pipeline_can_skip_optional_summary() -> None:
    analysis_input = load_analysis_input_fixture("AAPL")
    response = run_analysis_pipeline(analysis_input, include_summary=False)

    assert response.document_summary is None


def test_response_serializes_with_marketdata_alias() -> None:
    response = run_analysis_from_fixture("AAPL")
    payload = response.model_dump(by_alias=True, mode="json")

    assert "analysis_input" in payload
    assert "marketData" in payload["analysis_input"], (
        "AnalysisInput should preserve the camelCase marketData alias on the wire"
    )
