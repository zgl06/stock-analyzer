"""Print the normalized FinancialPeriod array for a ticker as a table.

Usage (from repo root with the venv active):
    python scripts/inspect_periods.py MSFT
"""

from __future__ import annotations

import json
import sys
import urllib.request

BASE_URL = "http://127.0.0.1:8000"


def _fmt_currency(value: float | None) -> str:
    if value is None:
        return "     n/a"
    return f"${value / 1_000_000_000:>7.2f}B"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "    n/a"
    return f"{value * 100:>+6.2f}%"


def main(ticker: str) -> int:
    url = f"{BASE_URL}/analysis-input/{ticker.upper()}"
    with urllib.request.urlopen(url, timeout=30) as response:
        payload = json.loads(response.read())

    periods = payload.get("financials", {}).get("periods", [])
    if not periods:
        print(f"No periods returned for {ticker}.")
        return 1

    header = f"{'period_end':>12}  {'fp':>4}  {'revenue':>12}  {'yoy':>8}  {'net_income':>12}  {'op_margin':>9}"
    print(header)
    print("-" * len(header))
    for period in periods:
        row = (
            f"{str(period.get('period_end', '')):>12}  "
            f"{str(period.get('fiscal_period', '')):>4}  "
            f"{_fmt_currency(period.get('revenue_usd')):>12}  "
            f"{_fmt_pct(period.get('revenue_yoy_growth')):>8}  "
            f"{_fmt_currency(period.get('net_income_usd')):>12}  "
            f"{_fmt_pct(period.get('operating_margin')):>9}"
        )
        print(row)

    growths = [
        p.get("revenue_yoy_growth")
        for p in periods
        if p.get("revenue_yoy_growth") is not None
    ]
    if growths:
        print()
        print(f"avg revenue YoY across {len(growths)} periods = {sum(growths)/len(growths)*100:+.2f}%")
    return 0


if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "MSFT"
    sys.exit(main(ticker))
