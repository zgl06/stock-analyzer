from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CompanySnapshot(BaseModel):
    """Static company metadata used throughout the analysis pipeline."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    ticker: str = Field(..., description="Primary US equity ticker symbol.")
    company_name: str = Field(..., description="Legal company name.")
    cik: str = Field(..., description="Zero-padded SEC Central Index Key.")
    exchange: str | None = Field(
        default=None,
        description="Primary listing exchange when available.",
    )
    sector: str | None = Field(
        default=None,
        description="Sector classification from the market data provider.",
    )
    industry: str | None = Field(
        default=None,
        description="Industry classification from the market data provider.",
    )
    currency: Literal["USD"] = Field(
        default="USD",
        description="Contract default for all monetary values.",
    )
    country: str | None = Field(
        default=None,
        description="Country of incorporation or headquarters.",
    )
    website: str | None = Field(
        default=None,
        description="Company website when known.",
    )


class FinancialPeriod(BaseModel):
    """Normalized point-in-time fundamentals for a reporting period."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    period_end: date
    fiscal_year: int
    fiscal_period: Literal["FY", "Q1", "Q2", "Q3", "Q4", "TTM"]
    revenue_usd: float | None = None
    net_income_usd: float | None = None
    diluted_eps: float | None = None
    gross_margin: float | None = Field(
        default=None,
        description="Stored as a decimal, e.g. 0.46 for 46%.",
    )
    operating_margin: float | None = Field(
        default=None,
        description="Stored as a decimal, e.g. 0.31 for 31%.",
    )
    free_cash_flow_usd: float | None = None
    cash_and_equivalents_usd: float | None = None
    total_debt_usd: float | None = None
    shares_outstanding: float | None = None
    revenue_yoy_growth: float | None = Field(
        default=None,
        description="Stored as a decimal, e.g. 0.08 for 8%.",
    )
    net_income_yoy_growth: float | None = Field(
        default=None,
        description="Stored as a decimal, e.g. 0.12 for 12%.",
    )


class NormalizedFinancials(BaseModel):
    """Historical and latest normalized fundamentals for analysis."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    reporting_basis: Literal["annual", "annual_plus_ttm"] = "annual_plus_ttm"
    latest_fiscal_year: int
    latest_fiscal_period: Literal["FY", "Q1", "Q2", "Q3", "Q4", "TTM"]
    periods: list[FinancialPeriod] = Field(
        default_factory=list,
        description="Ordered oldest to newest for consistent downstream use.",
    )


class FilingRecord(BaseModel):
    """Recent SEC filing metadata used for retrieval and qualitative analysis."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    accession_number: str
    filing_type: Literal["10-K", "10-Q", "8-K"]
    filing_date: date
    period_end: date | None = None
    filing_url: str
    primary_document_url: str | None = None
    description: str | None = None
    items: list[str] = Field(
        default_factory=list,
        description="Relevant 8-K items or parsed filing sections when available.",
    )


class MarketDataSnapshot(BaseModel):
    """Current market context and recent price history."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    as_of: datetime
    price_usd: float
    market_cap_usd: float | None = None
    enterprise_value_usd: float | None = None
    price_to_earnings: float | None = None
    price_to_sales: float | None = None
    dividend_yield: float | None = Field(
        default=None,
        description="Stored as a decimal, e.g. 0.0045 for 0.45%.",
    )
    fifty_two_week_high_usd: float | None = None
    fifty_two_week_low_usd: float | None = None
    historical_prices: list[float] = Field(
        default_factory=list,
        description="Daily adjusted close series ordered oldest to newest.",
    )


class AnalysisInput(BaseModel):
    """Shared handoff contract from ingestion to analysis."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    company: CompanySnapshot
    financials: NormalizedFinancials
    filings: list[FilingRecord]
    market_data: MarketDataSnapshot = Field(
        ...,
        alias="marketData",
        description="Market data payload for the analyzed ticker.",
    )
