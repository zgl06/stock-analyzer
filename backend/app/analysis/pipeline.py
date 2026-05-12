"""Analysis orchestrator.

Day 1: loads an `AnalysisInput` (from a fixture) and runs each
placeholder analysis module against it to produce a single assembled
`AnalysisResponse`. The orchestration boundary is intentionally
narrow so the input source can later be swapped from fixture to
stored normalized inputs without touching individual modules.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from backend.app.models import AnalysisInput, AnalysisResponse
from backend.app.services.fixture_loader import load_analysis_input_fixture

from .forecast import build_forecast
from .peers import select_peers
from .ranking import build_ranking_context
from .scoring import score_company
from .verdict import assemble_verdict


InputSource = Literal["fixture", "live"]


def run_analysis_pipeline(
    analysis_input: AnalysisInput,
    *,
    source: InputSource = "fixture",
) -> AnalysisResponse:
    """Run all analysis modules and assemble the response.

    document_summary is not populated here; it is attached by the route
    layer when enable_qualitative_summary is true (L3).
    """
    score = score_company(analysis_input)
    forecast = build_forecast(analysis_input)
    peers = select_peers(analysis_input)
    ranking_context = build_ranking_context(analysis_input, peers)
    verdict = assemble_verdict(analysis_input, score, forecast)

    return AnalysisResponse(
        ticker=analysis_input.company.ticker.upper(),
        generated_at=datetime.now(timezone.utc),
        source=source,
        company=analysis_input.company,
        analysis_input=analysis_input,
        score=score,
        forecast=forecast,
        peers=peers,
        ranking_context=ranking_context,
        verdict=verdict,
        document_summary=None,
    )


def run_analysis_from_fixture(ticker: str) -> AnalysisResponse:
    """Convenience entry point: load the fixture and run the pipeline."""
    analysis_input = load_analysis_input_fixture(ticker)
    return run_analysis_pipeline(analysis_input, source="fixture")
