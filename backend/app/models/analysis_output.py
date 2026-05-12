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
from .document_summary import DocumentSummary


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



class AmongPeersRanks(BaseModel):
    """Percentile standings of the subject within the subject plus peer set.

    Values are 0-100, higher means stronger vs the comparison set for that
    dimension (see methodology note on :class:`RankingContext`).
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    growth_percentile: float | None = Field(
        default=None,
        description="Percentile of YoY revenue growth within peer set.",
    )
    profitability_percentile: float | None = Field(
        default=None,
        description="Average percentile of gross and operating margin within peer set.",
    )
    valuation_percentile: float | None = Field(
        default=None,
        description="Percentile of P/S within peer set (higher = richer multiple).",
    )
    composite_proxy_percentile: float | None = Field(
        default=None,
        description="Equal-weight proxy across normalized growth, margins, and value vs peers.",
    )


class RankingContext(BaseModel):
    """Peer, industry, and broad-market rank context for the deep dashboard."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    among_peers: AmongPeersRanks = Field(
        default_factory=AmongPeersRanks,
        description="Ranks within the live peer set returned for this analysis.",
    )
    industry_universe_size: int | None = Field(
        default=None,
        description="Count of names used for the industry cohort (including subject).",
    )
    industry_percentile: float | None = Field(
        default=None,
        description="Proxy composite percentile within industry cohort, 0-100.",
    )
    market_universe_size: int | None = Field(
        default=None,
        description="Count of names in the market benchmark cohort (including subject).",
    )
    market_percentile: float | None = Field(
        default=None,
        description="Proxy composite percentile within market benchmark, 0-100.",
    )
    methodology_note: str = Field(
        default="Ranks use a simple normalized proxy of growth, margins, and multiples; not a model forecast.",
        description="How to interpret the numbers on the UI.",
    )


RelativeModelMethod = Literal["lightgbm", "score_proxy", "unavailable"]


class RelativeTercileEstimate(BaseModel):
    """Expected peer-relative tercile vs a benchmark (5y label definition in the spec)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    benchmark_ticker: str
    tercile: int | None = Field(
        default=None,
        description="1 = bottom third, 3 = top third of expected forward excess; None if unknown.",
    )
    score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Model-internal score 0-1 when available; maps to tercile.",
    )
    methodology: RelativeModelMethod = "unavailable"
    detail: str | None = None


class RelativePerformanceView(BaseModel):
    """Separate ML-facing view: vs SPY and vs GICS sector ETF; not the main long-term rating."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    horizon_years: int = Field(default=5, ge=1, le=10)
    as_of: str = Field(
        ...,
        description="ISO date: market / feature as-of; labels are 5y forward from here in training.",
    )
    gics_sector: str | None = None
    sector_etf: str | None = None
    used_parent_etf: bool = Field(
        default=False,
        description="True when a parent ETF replaced a missing sector series for labels only.",
    )
    vs_spy: RelativeTercileEstimate
    vs_sector: RelativeTercileEstimate
    feature_vector_version: str = Field(
        default="v1",
        description="Bumped when tabular feature columns change.",
    )
    llm_commentary: str | None = Field(
        default=None,
        description="Short narrative; numbers come only from the structured fields above.",
    )
    disclaimer: str = Field(
        default="Not investment advice. Estimates are experimental and not a guarantee of 5y excess return.",
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
        description="Input provenance marker; API routes use ``live`` for persisted Supabase data.",
    )
    company: CompanySnapshot
    analysis_input: AnalysisInput
    score: ScoreBreakdown
    forecast: list[ForecastScenario]
    peers: list[PeerComparison]
    ranking_context: RankingContext = Field(
        default_factory=RankingContext,
        description="Where the stock sits vs peers, industry, and a broad benchmark.",
    )
    verdict: InvestmentVerdict
    document_summary: DocumentSummary | None = None
    relative_performance: RelativePerformanceView | None = Field(
        default=None,
        description="5y forward-looking tercile view vs SPY and sector; separate from verdict.",
    )
    job: AnalysisJobStatus | None = Field(
        default=None,
        description="Latest job status when available; populated once async jobs land.",
    )


class PeersResponse(BaseModel):
    """Response for `GET /peers/{ticker}`: live peers plus ranking context."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    ticker: str
    company_name: str | None = None
    generated_at: datetime
    source: Literal["fixture", "live"]
    peers: list[PeerComparison]
    ranking_context: RankingContext
