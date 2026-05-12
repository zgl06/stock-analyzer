"""L1 RAG smoke test: index 1-2 filings for a ticker and run sample queries.

Usage:
    python -m backend.scripts.smoke_rag AAPL
    python -m backend.scripts.smoke_rag AAPL "supply chain risk"

Prereqs:
    1. pip install sentence-transformers beautifulsoup4
    2. Apply backend/migrations/001_filing_chunks.sql in Supabase
    3. backend/.env has SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY
    4. The ticker must have been analyzed once (so a row exists in `companies`).
       If not, run: curl http://localhost:8000/analysis/AAPL  (with backend running)
"""

from __future__ import annotations

import asyncio
import sys

from backend.app.config import get_settings
from backend.app.services.rag import RagService
from backend.app.services.sec import SecService


DEFAULT_QUERIES = [
    "supply chain risk",
    "revenue growth drivers",
    "litigation and legal proceedings",
    "asdfqwer xyzzy",  # gibberish — should return ~nothing
]


async def main(ticker: str, queries: list[str]) -> None:
    settings = get_settings()
    if not settings.has_supabase:
        print("ERROR: Supabase not configured. Check backend/.env.")
        sys.exit(1)

    rag = RagService(settings)
    sec = SecService(settings)

    company = await sec.resolve_company(ticker)
    print(f"\n[1/3] Resolved {ticker} -> CIK {company.cik}")

    rows = (
        rag.client.table("companies")
        .select("id")
        .eq("ticker", ticker.upper())
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        print(
            f"ERROR: No `companies` row for {ticker}. "
            f"Run an analysis first (GET /analysis/{ticker}) so it gets persisted."
        )
        sys.exit(1)
    company_id = rows[0]["id"]
    print(f"[1/3] Found company_id {company_id}")

    filings, _ = await sec.fetch_recent_filings(company.cik)
    target = [f for f in filings if f.filing_type == "10-K"][:1] + [
        f for f in filings if f.filing_type == "10-Q"
    ][:1]
    if not target:
        target = filings[:2]

    print(f"\n[2/3] Indexing {len(target)} filing(s)...")
    for filing in target:
        try:
            n = await rag.index_filing(company_id, filing)
            print(f"  {filing.filing_type} {filing.accession_number}: {n} chunks")
        except Exception as exc:
            print(f"  {filing.accession_number}: FAILED ({exc})")

    print(f"\n[3/3] Running {len(queries)} retrieval queries\n")
    for q in queries:
        print(f"--- query: {q!r}")
        results = await rag.retrieve(ticker, q, k=5, min_score=0.2)
        if not results:
            print("  (no chunks above min_score=0.2)\n")
            continue
        for i, c in enumerate(results, 1):
            preview = c.text[:200].replace("\n", " ")
            print(f"  [{i}] score={c.score:.3f} {c.filing_type} {c.filing_date}")
            print(f"      {preview}...")
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m backend.scripts.smoke_rag TICKER [query]")
        sys.exit(1)
    ticker = sys.argv[1].upper()
    queries = [sys.argv[2]] if len(sys.argv) > 2 else DEFAULT_QUERIES
    asyncio.run(main(ticker, queries))
