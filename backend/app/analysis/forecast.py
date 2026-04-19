"""Placeholder 3-5 year scenario forecast engine.

Day 1: returns deterministic bear / base / bull scenarios with stub
assumptions so the response shape is stable for downstream consumers.
"""

from __future__ import annotations

from backend.app.models import AnalysisInput, ForecastScenario


_HORIZON_YEARS = 5


def build_forecast(analysis_input: AnalysisInput) -> list[ForecastScenario]:
    """Return mock bear/base/bull scenarios for the given input."""
    _ = analysis_input

    return [
        ForecastScenario(
            scenario="bear",
            horizon_years=_HORIZON_YEARS,
            revenue_cagr=0.01,
            operating_margin_end=0.25,
            terminal_multiple=18.0,
            expected_annualized_return=-0.02,
            assumptions="Stub bear case pending real scenario model.",
        ),
        ForecastScenario(
            scenario="base",
            horizon_years=_HORIZON_YEARS,
            revenue_cagr=0.05,
            operating_margin_end=0.30,
            terminal_multiple=24.0,
            expected_annualized_return=0.07,
            assumptions="Stub base case pending real scenario model.",
        ),
        ForecastScenario(
            scenario="bull",
            horizon_years=_HORIZON_YEARS,
            revenue_cagr=0.09,
            operating_margin_end=0.34,
            terminal_multiple=30.0,
            expected_annualized_return=0.14,
            assumptions="Stub bull case pending real scenario model.",
        ),
    ]
