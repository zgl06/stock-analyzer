"""Parse SEC XBRL `companyfacts` payloads into per-period metric dicts.

The SEC publishes every XBRL-tagged fact a company has ever filed at
``https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json``. The structure
looks roughly like::

    {
      "facts": {
        "us-gaap": {
          "LongTermDebt": {
            "units": {
              "USD": [
                {"end": "2024-09-28", "val": 95000000000, "fy": 2024,
                 "fp": "FY", "form": "10-K", "filed": "2024-11-01",
                 "accn": "0000320193-24-000123"},
                ...
              ]
            }
          },
          "CashAndCashEquivalentsAtCarryingValue": {...},
          ...
        }
      }
    }

We're only interested in a handful of US-GAAP tags, and for each tag we
want the *most recent* restatement of each period-end value. This module
flattens the payload to ``{period_end_date: {metric_name: float}}`` so
``normalize.py`` can fill in whatever yfinance left as ``None``.

Why filter aggressively:
  * companyfacts payloads can be 5-20 MB for large filers; we only need
    a few values per period.
  * Every tag has many overlapping entries (the same fiscal year is
    reported in the original 10-K, then re-reported in subsequent 10-Qs
    and the next 10-K). Picking the latest ``filed`` date per ``end``
    ensures we use the most authoritative value.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable


# Internal field name -> ordered list of US-GAAP tag aliases. Earlier
# tags win when both are present (so we prefer the cleanest concept).
TAG_MAP: dict[str, tuple[str, ...]] = {
    "cash_and_equivalents_usd": (
        "CashAndCashEquivalentsAtCarryingValue",
        "Cash",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        "CashAndCashEquivalentsAtCarryingValueIncludingDiscontinuedOperations",
    ),
    "long_term_debt_usd": (
        "LongTermDebtNoncurrent",
        "LongTermDebt",
        "LongTermDebtAndCapitalLeaseObligations",
    ),
    "short_term_debt_usd": (
        "DebtCurrent",
        "ShortTermBorrowings",
        "LongTermDebtCurrent",
        "LongTermDebtAndCapitalLeaseObligationsCurrent",
    ),
    "revenue_usd": (
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ),
    "net_income_usd": (
        "NetIncomeLoss",
    ),
    "operating_income_usd": (
        "OperatingIncomeLoss",
    ),
    "gross_profit_usd": (
        "GrossProfit",
    ),
    "operating_cash_flow_usd": (
        "NetCashProvidedByUsedInOperatingActivities",
    ),
    "capex_usd": (
        "PaymentsToAcquirePropertyPlantAndEquipment",
    ),
}


# Forms we trust for fiscal-year values. 10-K is the gold standard;
# 10-K/A handles amendments. We also accept 20-F for foreign filers.
PREFERRED_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F"}


def extract_period_metrics(
    company_facts: dict[str, Any] | None,
) -> dict[date, dict[str, float]]:
    """Flatten a companyfacts payload to ``{period_end: {metric: value}}``.

    Only fiscal-year (FY) entries are kept and only for the tags we use.
    For each (tag, period_end) combination we keep the value from the
    most recently *filed* 10-K, which is how the SEC itself recommends
    consuming restated data.
    """
    if not company_facts:
        return {}

    us_gaap = (
        company_facts.get("facts", {}).get("us-gaap", {})
        if isinstance(company_facts.get("facts"), dict)
        else {}
    )
    if not us_gaap:
        return {}

    results: dict[date, dict[str, float]] = {}

    for metric_name, tag_aliases in TAG_MAP.items():
        for tag in tag_aliases:
            tag_data = us_gaap.get(tag)
            if not isinstance(tag_data, dict):
                continue

            usd_entries = tag_data.get("units", {}).get("USD")
            if not isinstance(usd_entries, list):
                continue

            for period_end, value in _best_values_per_period(usd_entries):
                bucket = results.setdefault(period_end, {})
                bucket.setdefault(metric_name, value)

    return results


def _best_values_per_period(
    entries: Iterable[dict[str, Any]],
) -> Iterable[tuple[date, float]]:
    """Yield ``(period_end, value)`` keeping the freshest FY 10-K per date."""
    best: dict[date, tuple[str, float]] = {}

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("fp", "")).upper() != "FY":
            continue
        form = str(entry.get("form", "")).strip()
        if form not in PREFERRED_FORMS:
            continue

        period_end = _parse_date(entry.get("end"))
        if period_end is None:
            continue

        value = _coerce_float(entry.get("val"))
        if value is None:
            continue

        filed = str(entry.get("filed", ""))
        existing = best.get(period_end)
        if existing is None or filed > existing[0]:
            best[period_end] = (filed, value)

    for period_end, (_, value) in best.items():
        yield period_end, value


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _coerce_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result != result:  # NaN check
        return None
    return result
