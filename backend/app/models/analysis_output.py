"""Downstream analysis-side contract.

Person 2 owns these types. They live in the same Pydantic model layer
as the ingestion handoff (`AnalysisInput`) so the backend has a single
source of truth for both sides of the contract.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .contracts import AnalysisInput, CompanySnapshot


ScorePillar = Literal[
    "business_quality",
    "growth",
    "profitability",
    "balance_sheet",
    "valuation",
]


LongTermRating = Literal["Strong Buy", "Buy", "Hold", "Avoid"]


ScenarioName = Literal["bear", "base", "bull"]


JobState = Literal["queued", "running", "completed", "failed"]


class PillarScore(BaseModel):
    """Single weighted pillar contributing to the composite score."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    pillar: ScorePillar
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Normalized pillar score in [0, 1].",
    )
    weight: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Weight applied to this pillar in the composite, in [0, 1].",
    )
    rationale: str | None = Field(
        default=None,
        description="Short human-readable explanation of how the score was derived.",
    )


class ScoreBreakdown(BaseModel):
    """Composite long-term score with explainable pillar contributions."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    composite_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Weighted composite score in [0, 1].",
    )
    pillars: list[PillarScore] = Field(
        default_factory=list,
        description="Per-pillar contributions ordered as displayed in the UI.",
    )
    methodology_version: str = Field(
        ...,
        description="Identifier for the scoring methodology that produced this output.",
    )


class ForecastScenario(BaseModel):
    """One scenario in the 3-5 year scenario model."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    scenario: ScenarioName
    horizon_years: int = Field(..., ge=1, le=10)
    revenue_cagr: float | None = Field(
        default=None,
        description="Assumed revenue CAGR over the horizon, decimal form.",
    )
    operating_margin_end: float | None = Field(
        default=None,
        description="Assumed end-of-horizon operating margin, decimal form.",
    )
    terminal_multiple: float | None = Field(
        default=None,
        description="Assumed terminal valuation multiple, e.g. P/E or EV/EBITDA.",
    )
    expected_annualized_return: float | None = Field(
        default=None,
        description="Annualized expected return implied by the scenario, decimal form.",
    )
    assumptions: str | None = Field(
        default=None,
        description="Short note on the qualitative assumptions behind the scenario.",
    )


class PeerComparison(BaseModel):
    """One peer line in the peer-comparison table."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    ticker: str
    company_name: str | None = None
    market_cap_usd: float | None = None
    revenue_yoy_growth: float | None = None
    gross_margin: float | None = None
    operating_margin: float | None = None
    price_to_earnings: float | None = None
    price_to_sales: float | None = None
    notes: str | None = None


class DocumentSummary(BaseModel):
    """Qualitative summary derived from filings and earnings text."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    management_tone: str | None = None
    guidance_direction: Literal["up", "down", "flat", "mixed", "unknown"] = "unknown"
    top_risks: list[str] = Field(default_factory=list)
    top_positives: list[str] = Field(default_factory=list)
    thesis_paragraph: str | None = Field(
        default=None,
        description="One-paragraph qualitative thesis suitable for the dashboard.",
    )
    source_filings: list[str] = Field(
        default_factory=list,
        description="Accession numbers of filings that contributed to this summary.",
    )
    available: bool = Field(
        default=True,
        description="False when the qualitative model layer was unavailable.",
    )


class InvestmentVerdict(BaseModel):
    """Final long-term recommendation surfaced on the dashboard."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    rating: LongTermRating
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence band in [0, 1] driven by data completeness and signal agreement.",
    )
    expected_return_low: float | None = Field(
        default=None,
        description="Lower bound of the expected annualized return range, decimal form.",
    )
    expected_return_high: float | None = Field(
        default=None,
        description="Upper bound of the expected annualized return range, decimal form.",
    )
    summary: str | None = Field(
        default=None,
        description="Short 'why this rating' explanation for the dashboard.",
    )


class AnalysisJobStatus(BaseModel):
    """Lifecycle record for an analysis job kicked off via POST /analyze/{ticker}."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    ticker: str
    state: JobState
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None


class AnalysisResponse(BaseModel):
    """Assembled response for GET /analysis/{ticker}.

    Wraps the input snapshot together with all downstream outputs
    so a single read covers everything the dashboard needs.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    ticker: str
    generated_at: datetime
    source: Literal["fixture", "live"] = Field(
        ...,
        description="Where the underlying AnalysisInput came from. Day 1 returns 'fixture'.",
    )
    company: CompanySnapshot
    analysis_input: AnalysisInput
    score: ScoreBreakdown
    forecast: list[ForecastScenario]
    peers: list[PeerComparison]
    verdict: InvestmentVerdict
    document_summary: DocumentSummary | None = None
    job: AnalysisJobStatus | None = Field(
        default=None,
        description="Latest job status when available; populated once async jobs land.",
    )
