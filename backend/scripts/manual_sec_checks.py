from __future__ import annotations

import asyncio
import sys
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from backend.app.config import get_settings
from backend.app.services.ingestion import run_ingestion
from backend.app.services.sec import RELEVANT_8K_ITEMS, SecService


DEFAULT_TICKER = "AAPL"
MAX_FILINGS_TO_PRINT = 5


async def main() -> int:
    ticker = _parse_ticker(sys.argv[1:])
    settings = get_settings()
    sec_service = SecService(settings)

    print(f"Manual Day 2 checks for ticker: {ticker}")
    print()

    try:
        company = await sec_service.resolve_company(ticker)
    except Exception as error:
        print("SEC lookup: FAILED")
        print(f"  Reason: {error}")
        return 1

    print("SEC lookup: OK")
    print(f"  ticker: {company.ticker}")
    print(f"  company_name: {company.company_name}")
    print(f"  cik: {company.cik}")
    print()

    try:
        filings, _ = await sec_service.fetch_recent_filings(company.cik)
    except Exception as error:
        print("SEC filing metadata fetch: FAILED")
        print(f"  Reason: {error}")
        return 1

    counts = Counter(filing.filing_type for filing in filings)
    has_core_filings = any(filing.filing_type in {"10-K", "10-Q"} for filing in filings)
    invalid_8k_filings = [
        filing
        for filing in filings
        if filing.filing_type == "8-K"
        and not any(item in RELEVANT_8K_ITEMS for item in filing.items)
    ]
    has_mixed_8k_items = any(
        filing.filing_type == "8-K"
        and any(item in RELEVANT_8K_ITEMS for item in filing.items)
        and any(item not in RELEVANT_8K_ITEMS for item in filing.items)
        for filing in filings
    )

    print("SEC filing metadata fetch: OK")
    print(f"  total_filings: {len(filings)}")
    print(
        "  filing_counts: "
        + ", ".join(f"{filing_type}={counts[filing_type]}" for filing_type in sorted(counts))
        if counts
        else "  filing_counts: none"
    )
    print(f"  has_recent_10K_or_10Q: {'yes' if has_core_filings else 'no'}")
    print(
        f"  8-K filings all have at least one relevant item: {'yes' if not invalid_8k_filings else 'no'}"
    )
    if has_mixed_8k_items:
        print("  note: mixed-item 8-Ks are allowed when they include at least one relevant item.")
    print()

    print(f"First {min(len(filings), MAX_FILINGS_TO_PRINT)} filing(s):")
    if not filings:
        print("  No supported filings returned.")
    for filing in filings[:MAX_FILINGS_TO_PRINT]:
        print(
            f"  - {filing.filing_type} | filing_date={filing.filing_date} | "
            f"period_end={filing.period_end} | items={filing.items or []}"
        )
        print(f"    filing_url={filing.filing_url}")
        print(f"    primary_document_url={filing.primary_document_url}")
    print()

    print("Ingestion composition check:")
    try:
        result = await run_ingestion(ticker)
        analysis_input = result.analysis_input
        print("  status: OK")
        print(f"  generated_at: {result.generated_at.isoformat()}")
        print(f"  analysis_input.company.ticker: {analysis_input.company.ticker}")
        print(f"  analysis_input.company.cik: {analysis_input.company.cik}")
        print(f"  analysis_input.filings_count: {len(analysis_input.filings)}")
        print(f"  analysis_input.market_data.price_usd: {analysis_input.market_data.price_usd}")
        print(f"  analysis_input.financial_periods: {len(analysis_input.financials.periods)}")
    except Exception as error:
        print("  status: WARNING")
        print(f"  reason: {error}")
        print("  note: SEC Day 2 checks can still be valid if ingestion fails due to market data or Supabase setup.")

    return 0


def _parse_ticker(args: list[str]) -> str:
    if not args:
        return DEFAULT_TICKER
    return args[0].strip().upper() or DEFAULT_TICKER


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
