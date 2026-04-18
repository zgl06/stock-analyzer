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
) -> AnalysisInput:
    financials = build_normalized_financials(market_raw_payload)
    return AnalysisInput(
        company=company,
        financials=financials,
        filings=filings,
        market_data=market_data,
    )


def build_normalized_financials(market_raw_payload: dict[str, Any]) -> NormalizedFinancials:
    periods = _build_periods_from_yfinance(market_raw_payload.get("financials", {}))
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


def _build_periods_from_yfinance(financials: dict[str, Any]) -> list[FinancialPeriod]:
    income_records = financials.get("income_stmt") or []
    balance_records = financials.get("balance_sheet") or []
    cashflow_records = financials.get("cashflow") or []

    balance_by_date = _records_by_date(balance_records)
    cashflow_by_date = _records_by_date(cashflow_records)

    periods: list[FinancialPeriod] = []
    for income_record in income_records:
        period_end = _extract_date(income_record.get("index"))
        if not period_end:
            continue

        balance_record = balance_by_date.get(period_end.isoformat(), {})
        cashflow_record = cashflow_by_date.get(period_end.isoformat(), {})

        revenue = _pick_number(
            income_record,
            "Total Revenue",
            "Operating Revenue",
            "Revenue",
        )
        net_income = _pick_number(income_record, "Net Income", "Net Income Common Stockholders")
        gross_profit = _pick_number(income_record, "Gross Profit")
        operating_income = _pick_number(income_record, "Operating Income")

        gross_margin = gross_profit / revenue if gross_profit is not None and revenue else None
        operating_margin = (
            operating_income / revenue if operating_income is not None and revenue else None
        )

        period = FinancialPeriod(
            period_end=period_end,
            fiscal_year=period_end.year,
            fiscal_period="FY",
            revenue_usd=revenue,
            net_income_usd=net_income,
            diluted_eps=_pick_number(income_record, "Diluted EPS", "Basic EPS"),
            gross_margin=gross_margin,
            operating_margin=operating_margin,
            free_cash_flow_usd=_compute_free_cash_flow(cashflow_record),
            cash_and_equivalents_usd=_pick_number(
                balance_record,
                "Cash And Cash Equivalents",
                "Cash Cash Equivalents And Short Term Investments",
                "Cash Equivalents",
            ),
            total_debt_usd=_pick_number(
                balance_record,
                "Total Debt",
                "Long Term Debt",
                "Current Debt",
            ),
            shares_outstanding=_pick_number(
                income_record,
                "Diluted Average Shares",
                "Basic Average Shares",
                "Ordinary Shares Number",
            ),
        )
        periods.append(period)

    periods = _add_growth_rates(periods)
    if periods:
        periods[-1] = periods[-1].model_copy(update={"fiscal_period": "TTM"})
    return periods


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
