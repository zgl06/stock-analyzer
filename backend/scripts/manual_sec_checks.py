from __future__ import annotations

import asyncio
import sys
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from backend.app.config import get_settings
from backend.app.errors import AppError
from backend.app.services.ingestion import run_ingestion
from backend.app.services.sec import RELEVANT_8K_ITEMS, SecService


DEFAULT_TICKERS = ("AAPL", "JPM", "PLUG")
MAX_FILINGS_TO_PRINT = 5


async def main() -> int:
    tickers = _parse_tickers(sys.argv[1:])
    exit_code = 0
    for ticker in tickers:
        status = await _run_checks_for_ticker(ticker)
        exit_code = max(exit_code, status)
        print()
    return exit_code


async def _run_checks_for_ticker(ticker: str) -> int:
    settings = get_settings()
    sec_service = SecService(settings)

    print(f"Manual Person 1 checks for ticker: {ticker}")
    print()

    try:
        company = await sec_service.resolve_company(ticker)
        print("SEC lookup: PASS")
        print(f"  ticker: {company.ticker}")
        print(f"  company_name: {company.company_name}")
        print(f"  cik: {company.cik}")
    except Exception as error:
        print("SEC lookup: FAIL")
        print(f"  reason: {error}")
        return 1
    print()

    try:
        filings, _ = await sec_service.fetch_recent_filings(company.cik)
        print("SEC filing metadata fetch: PASS")
        _print_filing_summary(filings)
    except Exception as error:
        print("SEC filing metadata fetch: FAIL")
        print(f"  reason: {error}")
        return 1
    print()

    print("Ingestion contract check:")
    try:
        result = await run_ingestion(ticker)
        analysis_input = result.analysis_input
        print("  ingestion: PASS")
        print(f"  generated_at: {result.generated_at.isoformat()}")
        print(f"  company resolution: PASS ({analysis_input.company.ticker})")
        print(
            f"  filings present: {'PASS' if analysis_input.filings else 'FAIL'} "
            f"({len(analysis_input.filings)})"
        )
        print(
            f"  price present: {'PASS' if analysis_input.market_data.price_usd > 0 else 'FAIL'} "
            f"({analysis_input.market_data.price_usd})"
        )
        print(
            f"  normalized periods present: "
            f"{'PASS' if analysis_input.financials.periods else 'FAIL'} "
            f"({len(analysis_input.financials.periods)})"
        )
        if settings.has_supabase:
            print("  persistence: PASS or attempted (see service logs for exact insert result)")
        else:
            print("  persistence: SKIPPED (Supabase is not configured)")
    except AppError as error:
        print("  ingestion: FAIL")
        print(f"  reason: {error.message}")
        if not settings.has_supabase:
            print("  persistence: SKIPPED (Supabase is not configured)")
        return 1
    except Exception as error:
        print("  ingestion: FAIL")
        print(f"  reason: {error}")
        if not settings.has_supabase:
            print("  persistence: SKIPPED (Supabase is not configured)")
        return 1

    return 0


def _print_filing_summary(filings) -> None:
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

    print(f"  first {min(len(filings), MAX_FILINGS_TO_PRINT)} filing(s):")
    if not filings:
        print("    No supported filings returned.")
    for filing in filings[:MAX_FILINGS_TO_PRINT]:
        print(
            f"    - {filing.filing_type} | filing_date={filing.filing_date} | "
            f"period_end={filing.period_end} | items={filing.items or []}"
        )
        print(f"      filing_url={filing.filing_url}")
        print(f"      primary_document_url={filing.primary_document_url}")


def _parse_tickers(args: list[str]) -> list[str]:
    if not args:
        return list(DEFAULT_TICKERS)
    return [arg.strip().upper() for arg in args if arg.strip()]


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
