"""Placeholder verdict-assembly module.

Day 1: combines stub score and forecast into a deterministic
`InvestmentVerdict`. Real rating thresholds and confidence weighting
land in a later day.
"""

from __future__ import annotations

from backend.app.models import (
    AnalysisInput,
    ForecastScenario,
    InvestmentVerdict,
    LongTermRating,
    ScoreBreakdown,
)


def _rating_from_score(composite_score: float) -> LongTermRating:
    if composite_score >= 0.80:
        return "Strong Buy"
    if composite_score >= 0.60:
        return "Buy"
    if composite_score >= 0.40:
        return "Hold"
    return "Avoid"


def assemble_verdict(
    analysis_input: AnalysisInput,
    score: ScoreBreakdown,
    forecast: list[ForecastScenario],
) -> InvestmentVerdict:
    """Return a mock verdict derived from the stub score and forecast."""
    _ = analysis_input

    bear = next((s for s in forecast if s.scenario == "bear"), None)
    bull = next((s for s in forecast if s.scenario == "bull"), None)

    rating = _rating_from_score(score.composite_score)

    return InvestmentVerdict(
        rating=rating,
        confidence=0.5,
        expected_return_low=bear.expected_annualized_return if bear else None,
        expected_return_high=bull.expected_annualized_return if bull else None,
        summary=(
            "Stub verdict assembled from placeholder score and forecast. "
            "Real rationale pending downstream implementation."
        ),
    )
