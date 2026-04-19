"""Deterministic scoring engine.

Day 2: replaces the Day 1 stub with explainable, fixed-weight pillar
scoring computed from `AnalysisInput`. Each pillar lands in `[0, 1]`
and is blended into a composite via centrally-defined MVP weights.

Scoring is intentionally simple, transparent, and deterministic:
- same input always yields the same output
- missing/null fields degrade to neutral defaults instead of raising
- formulas use only fields already present in the shared contract
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.models import (
    AnalysisInput,
    FinancialPeriod,
    MarketDataSnapshot,
    PillarScore,
    ScoreBreakdown,
    ScorePillar,
)


METHODOLOGY_VERSION = "deterministic-v1"


PILLAR_WEIGHTS: dict[ScorePillar, float] = {
    "business_quality": 0.20,
    "growth": 0.20,
    "profitability": 0.20,
    "balance_sheet": 0.15,
    "valuation": 0.25,
}


PILLAR_ORDER: tuple[ScorePillar, ...] = (
    "business_quality",
    "growth",
    "profitability",
    "balance_sheet",
    "valuation",
)


NEUTRAL_SCORE = 0.5


@dataclass(frozen=True)
class _PillarResult:
    score: float
    rationale: str


def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _latest_period(analysis_input: AnalysisInput) -> FinancialPeriod | None:
    periods = analysis_input.financials.periods
    if not periods:
        return None
    return periods[-1]


def _score_business_quality(latest: FinancialPeriod | None) -> _PillarResult:
    """Margin-quality proxy from gross and operating margins."""
    if latest is None or (latest.gross_margin is None and latest.operating_margin is None):
        return _PillarResult(NEUTRAL_SCORE, "No margin data available; neutral default applied.")

    parts: list[float] = []
    notes: list[str] = []

    if latest.gross_margin is not None:
        gm_norm = _clamp01((latest.gross_margin - 0.10) / 0.60)
        parts.append(gm_norm)
        notes.append(f"gross margin {latest.gross_margin:.0%}")

    if latest.operating_margin is not None:
        om_norm = _clamp01((latest.operating_margin - 0.05) / 0.30)
        parts.append(om_norm)
        notes.append(f"operating margin {latest.operating_margin:.0%}")

    score = sum(parts) / len(parts) if parts else NEUTRAL_SCORE
    return _PillarResult(score, "Business quality from " + " and ".join(notes) + ".")


def _score_growth(periods: list[FinancialPeriod]) -> _PillarResult:
    """Growth from average revenue YoY plus the latest net income YoY."""
    if not periods:
        return _PillarResult(NEUTRAL_SCORE, "No periods available; neutral default applied.")

    rev_growths = [p.revenue_yoy_growth for p in periods if p.revenue_yoy_growth is not None]
    latest = periods[-1]

    parts: list[float] = []
    notes: list[str] = []

    if rev_growths:
        avg_rev_growth = sum(rev_growths) / len(rev_growths)
        rev_norm = _clamp01((avg_rev_growth + 0.05) / 0.30)
        parts.append(rev_norm)
        notes.append(f"avg revenue YoY {avg_rev_growth:.1%}")

    if latest.net_income_yoy_growth is not None:
        ni_norm = _clamp01((latest.net_income_yoy_growth + 0.05) / 0.30)
        parts.append(ni_norm)
        notes.append(f"latest net income YoY {latest.net_income_yoy_growth:.1%}")

    if not parts:
        return _PillarResult(NEUTRAL_SCORE, "No growth data available; neutral default applied.")

    score = sum(parts) / len(parts)
    return _PillarResult(score, "Growth from " + " and ".join(notes) + ".")


def _score_profitability(latest: FinancialPeriod | None) -> _PillarResult:
    """Bottom-line profitability from net income and free cash flow margins."""
    if latest is None or not latest.revenue_usd:
        return _PillarResult(NEUTRAL_SCORE, "No revenue available for profitability ratios; neutral default applied.")

    parts: list[float] = []
    notes: list[str] = []

    if latest.net_income_usd is not None:
        ni_margin = latest.net_income_usd / latest.revenue_usd
        ni_norm = _clamp01(ni_margin / 0.25)
        parts.append(ni_norm)
        notes.append(f"net margin {ni_margin:.0%}")

    if latest.free_cash_flow_usd is not None:
        fcf_margin = latest.free_cash_flow_usd / latest.revenue_usd
        fcf_norm = _clamp01(fcf_margin / 0.25)
        parts.append(fcf_norm)
        notes.append(f"FCF margin {fcf_margin:.0%}")

    if not parts:
        return _PillarResult(NEUTRAL_SCORE, "No profitability data available; neutral default applied.")

    score = sum(parts) / len(parts)
    return _PillarResult(score, "Profitability from " + " and ".join(notes) + ".")


def _score_balance_sheet(latest: FinancialPeriod | None) -> _PillarResult:
    """Balance-sheet strength from net debt scaled by revenue."""
    if latest is None or not latest.revenue_usd:
        return _PillarResult(NEUTRAL_SCORE, "No revenue available for leverage ratios; neutral default applied.")

    debt = latest.total_debt_usd
    cash = latest.cash_and_equivalents_usd

    if debt is None and cash is None:
        return _PillarResult(NEUTRAL_SCORE, "No balance-sheet data available; neutral default applied.")

    debt_val = debt if debt is not None else 0.0
    cash_val = cash if cash is not None else 0.0
    net_debt = debt_val - cash_val
    net_debt_to_rev = net_debt / latest.revenue_usd

    score = _clamp01(1.0 - ((net_debt_to_rev + 0.5) / 2.0))
    rationale = (
        f"Net debt/revenue {net_debt_to_rev:.2f} "
        f"(debt {debt_val:,.0f}, cash {cash_val:,.0f})."
    )
    return _PillarResult(score, rationale)


def _score_valuation(market: MarketDataSnapshot) -> _PillarResult:
    """Valuation from price-to-earnings and price-to-sales (lower is better)."""
    parts: list[float] = []
    notes: list[str] = []

    if market.price_to_earnings is not None and market.price_to_earnings > 0:
        pe_norm = _clamp01(1.0 - (market.price_to_earnings - 10.0) / 30.0)
        parts.append(pe_norm)
        notes.append(f"P/E {market.price_to_earnings:.1f}")

    if market.price_to_sales is not None and market.price_to_sales > 0:
        ps_norm = _clamp01(1.0 - (market.price_to_sales - 1.0) / 15.0)
        parts.append(ps_norm)
        notes.append(f"P/S {market.price_to_sales:.1f}")

    if not parts:
        return _PillarResult(NEUTRAL_SCORE, "No valuation multiples available; neutral default applied.")

    score = sum(parts) / len(parts)
    return _PillarResult(score, "Valuation from " + " and ".join(notes) + ".")


_PILLAR_FUNCTIONS = {
    "business_quality": lambda ai: _score_business_quality(_latest_period(ai)),
    "growth": lambda ai: _score_growth(ai.financials.periods),
    "profitability": lambda ai: _score_profitability(_latest_period(ai)),
    "balance_sheet": lambda ai: _score_balance_sheet(_latest_period(ai)),
    "valuation": lambda ai: _score_valuation(ai.market_data),
}


def score_company(analysis_input: AnalysisInput) -> ScoreBreakdown:
    """Compute the deterministic weighted score for an analysis input."""
    pillars: list[PillarScore] = []
    for pillar_name in PILLAR_ORDER:
        result = _PILLAR_FUNCTIONS[pillar_name](analysis_input)
        pillars.append(
            PillarScore(
                pillar=pillar_name,
                score=round(_clamp01(result.score), 4),
                weight=PILLAR_WEIGHTS[pillar_name],
                rationale=result.rationale,
            )
        )

    composite = sum(p.score * p.weight for p in pillars)

    return ScoreBreakdown(
        composite_score=round(_clamp01(composite), 4),
        pillars=pillars,
        methodology_version=METHODOLOGY_VERSION,
    )
