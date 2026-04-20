"""Deterministic 3-5 year scenario forecast engine.

Day 3: replaces the Day 1 stub with explainable bear / base / bull
scenarios computed from `AnalysisInput`. The model is intentionally
small and transparent:

- scenario inputs (revenue CAGR, terminal operating margin, terminal
  P/E) are derived from the latest period plus historical YoY growth
- expected annualized return is computed from a textbook
  revenue -> earnings -> terminal market cap projection
- missing or unusable inputs degrade to neutral defaults instead of
  raising; ``expected_annualized_return`` becomes ``None`` when the
  current market cap can't be derived

Same input always yields the same output, and bear <= base <= bull
holds for every numeric field by construction.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.models import (
    AnalysisInput,
    FinancialPeriod,
    ForecastScenario,
    MarketDataSnapshot,
    NormalizedFinancials,
    ScenarioName,
)


METHODOLOGY_VERSION = "scenarios-v1"

HORIZON_YEARS = 5

EFFECTIVE_TAX_RATE = 0.21

DEFAULT_REVENUE_GROWTH = 0.05
DEFAULT_OPERATING_MARGIN = 0.15
DEFAULT_TERMINAL_MULTIPLE = 20.0

REVENUE_CAGR_BOUNDS = (-0.10, 0.40)
OPERATING_MARGIN_BOUNDS = (0.0, 0.60)
TERMINAL_MULTIPLE_BOUNDS = (5.0, 50.0)
EXPECTED_RETURN_BOUNDS = (-0.30, 0.50)


@dataclass(frozen=True)
class _ScenarioDeltas:
    growth_delta: float
    margin_delta: float
    multiple_delta: float
    label: str


SCENARIO_DELTAS: dict[ScenarioName, _ScenarioDeltas] = {
    "bear": _ScenarioDeltas(
        growth_delta=-0.04,
        margin_delta=-0.03,
        multiple_delta=-5.0,
        label="conservative",
    ),
    "base": _ScenarioDeltas(
        growth_delta=0.0,
        margin_delta=0.0,
        multiple_delta=0.0,
        label="central",
    ),
    "bull": _ScenarioDeltas(
        growth_delta=0.04,
        margin_delta=0.03,
        multiple_delta=5.0,
        label="optimistic",
    ),
}


SCENARIO_ORDER: tuple[ScenarioName, ...] = ("bear", "base", "bull")


def _clamp(value: float, bounds: tuple[float, float]) -> float:
    low, high = bounds
    if value < low:
        return low
    if value > high:
        return high
    return value


def _latest_period(financials: NormalizedFinancials) -> FinancialPeriod | None:
    return financials.periods[-1] if financials.periods else None


def _average_revenue_growth(financials: NormalizedFinancials) -> float:
    growths = [
        period.revenue_yoy_growth
        for period in financials.periods
        if period.revenue_yoy_growth is not None
    ]
    if not growths:
        return DEFAULT_REVENUE_GROWTH
    return sum(growths) / len(growths)


def _current_market_cap(market: MarketDataSnapshot, latest: FinancialPeriod | None) -> float | None:
    if market.market_cap_usd is not None and market.market_cap_usd > 0:
        return market.market_cap_usd
    shares = latest.shares_outstanding if latest else None
    if shares is not None and shares > 0 and market.price_usd > 0:
        return market.price_usd * shares
    return None


def _baseline_inputs(analysis_input: AnalysisInput) -> tuple[float, float, float]:
    """Return (avg_growth, base_op_margin, base_terminal_multiple)."""
    latest = _latest_period(analysis_input.financials)

    avg_growth = _average_revenue_growth(analysis_input.financials)

    base_op_margin = (
        latest.operating_margin
        if latest is not None and latest.operating_margin is not None
        else DEFAULT_OPERATING_MARGIN
    )

    pe_latest = analysis_input.market_data.price_to_earnings
    base_multiple = (
        pe_latest if pe_latest is not None and pe_latest > 0 else DEFAULT_TERMINAL_MULTIPLE
    )

    return avg_growth, base_op_margin, base_multiple


def _projected_return(
    *,
    revenue_0: float | None,
    revenue_cagr: float,
    operating_margin_end: float,
    terminal_multiple: float,
    current_market_cap: float | None,
) -> float | None:
    """Return scenario annualized return from a textbook projection.

    revenue_T = revenue_0 * (1 + cagr)^T
    earnings_T = revenue_T * operating_margin_end * (1 - tax_rate)
    future_mcap = earnings_T * terminal_multiple
    annualized = (future_mcap / current_mcap)^(1 / T) - 1
    """
    if revenue_0 is None or revenue_0 <= 0:
        return None
    if current_market_cap is None or current_market_cap <= 0:
        return None

    revenue_t = revenue_0 * (1.0 + revenue_cagr) ** HORIZON_YEARS
    earnings_t = revenue_t * operating_margin_end * (1.0 - EFFECTIVE_TAX_RATE)
    future_mcap = earnings_t * terminal_multiple

    if future_mcap <= 0:
        return EXPECTED_RETURN_BOUNDS[0]

    raw = (future_mcap / current_market_cap) ** (1.0 / HORIZON_YEARS) - 1.0
    return _clamp(raw, EXPECTED_RETURN_BOUNDS)


def _build_scenario(
    name: ScenarioName,
    *,
    avg_growth: float,
    base_op_margin: float,
    base_multiple: float,
    revenue_0: float | None,
    current_market_cap: float | None,
) -> ForecastScenario:
    deltas = SCENARIO_DELTAS[name]

    revenue_cagr = _clamp(avg_growth + deltas.growth_delta, REVENUE_CAGR_BOUNDS)
    operating_margin_end = _clamp(
        base_op_margin + deltas.margin_delta, OPERATING_MARGIN_BOUNDS
    )
    terminal_multiple = _clamp(
        base_multiple + deltas.multiple_delta, TERMINAL_MULTIPLE_BOUNDS
    )

    expected_return = _projected_return(
        revenue_0=revenue_0,
        revenue_cagr=revenue_cagr,
        operating_margin_end=operating_margin_end,
        terminal_multiple=terminal_multiple,
        current_market_cap=current_market_cap,
    )

    assumptions = (
        f"{deltas.label.capitalize()} case: revenue CAGR {revenue_cagr:.1%}, "
        f"terminal operating margin {operating_margin_end:.0%}, "
        f"terminal P/E {terminal_multiple:.1f}x over {HORIZON_YEARS}y "
        f"(after-tax earnings, tax rate {EFFECTIVE_TAX_RATE:.0%})."
    )

    return ForecastScenario(
        scenario=name,
        horizon_years=HORIZON_YEARS,
        revenue_cagr=round(revenue_cagr, 4),
        operating_margin_end=round(operating_margin_end, 4),
        terminal_multiple=round(terminal_multiple, 2),
        expected_annualized_return=(
            round(expected_return, 4) if expected_return is not None else None
        ),
        assumptions=assumptions,
    )


def build_forecast(analysis_input: AnalysisInput) -> list[ForecastScenario]:
    """Return deterministic bear/base/bull scenarios for the given input."""
    latest = _latest_period(analysis_input.financials)
    avg_growth, base_op_margin, base_multiple = _baseline_inputs(analysis_input)
    revenue_0 = latest.revenue_usd if latest is not None else None
    current_market_cap = _current_market_cap(analysis_input.market_data, latest)

    return [
        _build_scenario(
            name,
            avg_growth=avg_growth,
            base_op_margin=base_op_margin,
            base_multiple=base_multiple,
            revenue_0=revenue_0,
            current_market_cap=current_market_cap,
        )
        for name in SCENARIO_ORDER
    ]
