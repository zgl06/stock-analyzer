from __future__ import annotations

from datetime import date
import math
from typing import Any

from backend.app.models import (
    AnalysisInput,
    CompanySnapshot,
    FilingRecord,
    MarketDataSnapshot,
    NormalizedFinancials,
)
from backend.app.models.contracts import FinancialPeriod


def build_analysis_input(
    company: CompanySnapshot,
    filings: list[FilingRecord],
    market_data: MarketDataSnapshot,
    market_raw_payload: dict[str, Any],
    sec_period_metrics: dict[date, dict[str, float]] | None = None,
) -> AnalysisInput:
    financials = build_normalized_financials(
        market_raw_payload,
        sec_period_metrics=sec_period_metrics,
    )
    return AnalysisInput(
        company=company,
        financials=financials,
        filings=filings,
        market_data=market_data,
    )


def build_normalized_financials(
    market_raw_payload: dict[str, Any],
    sec_period_metrics: dict[date, dict[str, float]] | None = None,
) -> NormalizedFinancials:
    periods = _build_periods_from_yfinance(
        market_raw_payload.get("financials", {}),
        sec_period_metrics=sec_period_metrics or {},
    )
    if periods:
        periods = sorted(periods, key=lambda period: period.period_end)
        latest = periods[-1]
        return NormalizedFinancials(
            reporting_basis="annual_plus_ttm",
            latest_fiscal_year=latest.fiscal_year,
            latest_fiscal_period=latest.fiscal_period,
            periods=periods,
        )

    today = date.today()
    return NormalizedFinancials(
        reporting_basis="annual_plus_ttm",
        latest_fiscal_year=today.year,
        latest_fiscal_period="TTM",
        periods=[
            FinancialPeriod(
                period_end=today,
                fiscal_year=today.year,
                fiscal_period="TTM",
            )
        ],
    )


def _build_periods_from_yfinance(
    financials: dict[str, Any],
    sec_period_metrics: dict[date, dict[str, float]] | None = None,
) -> list[FinancialPeriod]:
    income_records = financials.get("income_stmt") or []
    balance_records = financials.get("balance_sheet") or []
    cashflow_records = financials.get("cashflow") or []

    balance_by_date = _records_by_date(balance_records)
    cashflow_by_date = _records_by_date(cashflow_records)
    sec_metrics = sec_period_metrics or {}

    periods: list[FinancialPeriod] = []
    for income_record in income_records:
        period_end = _extract_date(income_record.get("index"))
        if not period_end:
            continue

        balance_record = balance_by_date.get(period_end.isoformat(), {})
        cashflow_record = cashflow_by_date.get(period_end.isoformat(), {})
        sec_for_period = sec_metrics.get(period_end, {})

        revenue = _pick_number(
            income_record,
            "Total Revenue",
            "Operating Revenue",
            "Revenue",
        ) or sec_for_period.get("revenue_usd")
        net_income = _pick_number(
            income_record, "Net Income", "Net Income Common Stockholders"
        ) or sec_for_period.get("net_income_usd")
        gross_profit = _pick_number(
            income_record, "Gross Profit"
        ) or sec_for_period.get("gross_profit_usd")
        operating_income = _pick_number(
            income_record, "Operating Income"
        ) or sec_for_period.get("operating_income_usd")

        gross_margin = gross_profit / revenue if gross_profit is not None and revenue else None
        operating_margin = (
            operating_income / revenue if operating_income is not None and revenue else None
        )

        cash = _pick_cash(balance_record)
        if cash is None:
            cash = sec_for_period.get("cash_and_equivalents_usd")

        total_debt = _pick_total_debt(balance_record)
        if total_debt is None:
            total_debt = _sec_total_debt(sec_for_period)

        free_cash_flow = _compute_free_cash_flow(cashflow_record)
        if free_cash_flow is None:
            free_cash_flow = _sec_free_cash_flow(sec_for_period)

        period = FinancialPeriod(
            period_end=period_end,
            fiscal_year=period_end.year,
            fiscal_period="FY",
            revenue_usd=revenue,
            net_income_usd=net_income,
            diluted_eps=_pick_number(income_record, "Diluted EPS", "Basic EPS"),
            gross_margin=gross_margin,
            operating_margin=operating_margin,
            free_cash_flow_usd=free_cash_flow,
            cash_and_equivalents_usd=cash,
            total_debt_usd=total_debt,
            shares_outstanding=_pick_number(
                income_record,
                "Diluted Average Shares",
                "Basic Average Shares",
                "Ordinary Shares Number",
            ),
        )
        periods.append(period)

    # If yfinance returned no income statement at all, fall back to
    # period-ends from SEC company facts so we still get *some* history.
    if not periods and sec_metrics:
        periods = _build_periods_from_sec_only(sec_metrics)

    periods = _add_growth_rates(periods)
    if periods:
        periods[-1] = periods[-1].model_copy(update={"fiscal_period": "TTM"})
    return periods


def _build_periods_from_sec_only(
    sec_metrics: dict[date, dict[str, float]],
) -> list[FinancialPeriod]:
    periods: list[FinancialPeriod] = []
    for period_end in sorted(sec_metrics.keys()):
        metrics = sec_metrics[period_end]
        revenue = metrics.get("revenue_usd")
        net_income = metrics.get("net_income_usd")
        gross_profit = metrics.get("gross_profit_usd")
        operating_income = metrics.get("operating_income_usd")

        gross_margin = (
            gross_profit / revenue if gross_profit is not None and revenue else None
        )
        operating_margin = (
            operating_income / revenue
            if operating_income is not None and revenue
            else None
        )

        periods.append(
            FinancialPeriod(
                period_end=period_end,
                fiscal_year=period_end.year,
                fiscal_period="FY",
                revenue_usd=revenue,
                net_income_usd=net_income,
                gross_margin=gross_margin,
                operating_margin=operating_margin,
                free_cash_flow_usd=_sec_free_cash_flow(metrics),
                cash_and_equivalents_usd=metrics.get("cash_and_equivalents_usd"),
                total_debt_usd=_sec_total_debt(metrics),
            )
        )
    return periods


def _sec_total_debt(metrics: dict[str, float]) -> float | None:
    long_term = metrics.get("long_term_debt_usd")
    short_term = metrics.get("short_term_debt_usd")
    if long_term is None and short_term is None:
        return None
    return (long_term or 0.0) + (short_term or 0.0)


def _sec_free_cash_flow(metrics: dict[str, float]) -> float | None:
    operating = metrics.get("operating_cash_flow_usd")
    capex = metrics.get("capex_usd")
    if operating is None:
        return None
    if capex is None:
        return operating
    return operating - abs(capex)


def _records_by_date(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for record in records:
        period_key = record.get("index")
        if isinstance(period_key, str):
            output[period_key] = record
    return output


def _extract_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _pick_number(record: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key not in record or record[key] is None:
            continue
        try:
            value = float(record[key])
        except (TypeError, ValueError):
            continue
        if not math.isfinite(value):
            continue
        return value
    return None


def _compute_free_cash_flow(record: dict[str, Any]) -> float | None:
    operating = _pick_number(record, "Operating Cash Flow", "Cash Flow From Continuing Operating Activities")
    capex = _pick_number(record, "Capital Expenditure", "Capital Expenditures")
    if operating is None:
        return None
    if capex is None:
        return operating
    return operating - abs(capex)


# yfinance balance-sheet labels vary widely across industries and report
# vintages, so we try a generous list of aliases. If no aggregate "Total Debt"
# style field is present we fall back to summing long-term + short-term/current
# debt components, including capital-lease variants used by industrials.
def _pick_cash(record: dict[str, Any]) -> float | None:
    return _pick_number(
        record,
        "Cash And Cash Equivalents",
        "Cash Cash Equivalents And Short Term Investments",
        "Cash Equivalents",
        "Cash Financial",
        "Cash",
    )


def _pick_total_debt(record: dict[str, Any]) -> float | None:
    aggregate = _pick_number(
        record,
        "Total Debt",
        "Net Debt",
    )
    if aggregate is not None:
        return aggregate

    long_term = _pick_number(
        record,
        "Long Term Debt And Capital Lease Obligation",
        "Long Term Debt",
        "Long Term Capital Lease Obligation",
    )
    short_term = _pick_number(
        record,
        "Current Debt And Capital Lease Obligation",
        "Current Debt",
        "Short Long Term Debt",
        "Current Capital Lease Obligation",
    )

    if long_term is None and short_term is None:
        return None
    return (long_term or 0.0) + (short_term or 0.0)


def _add_growth_rates(periods: list[FinancialPeriod]) -> list[FinancialPeriod]:
    updated: list[FinancialPeriod] = []
    for index, period in enumerate(periods):
        previous = periods[index - 1] if index > 0 else None
        revenue_growth = _growth(period.revenue_usd, previous.revenue_usd) if previous else None
        net_income_growth = (
            _growth(period.net_income_usd, previous.net_income_usd) if previous else None
        )
        updated.append(
            period.model_copy(
                update={
                    "revenue_yoy_growth": revenue_growth,
                    "net_income_yoy_growth": net_income_growth,
                }
            )
        )
    return updated


def _growth(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    result = (current - previous) / abs(previous)
    if not math.isfinite(result):
        return None
    return result
