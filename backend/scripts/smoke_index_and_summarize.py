"""One-shot L1+L2 smoke: index a ticker if needed, then summarize.

Usage:
    python -m backend.scripts.smoke_index_and_summarize AAPL
    python -m backend.scripts.smoke_index_and_summarize NVDA INTC JNJ DIS NKE

Behavior:
    For each ticker:
      1. Ensure a `companies` row exists (resolves CIK via SecService).
      2. Count existing rows in `filing_chunks` for that company.
      3. If fewer than MIN_CHUNKS, fetch the latest 10-K and 10-Q and index them.
      4. Call QualitativeService.summarize and print the resulting JSON.

Prereqs:
    - Supabase configured in backend/.env, migrations 001 + 002 applied.
    - Ollama running with the configured model pulled.
"""

from __future__ import annotations

import asyncio
import json
import sys

from backend.app.config import get_settings
from backend.app.services.ollama_client import OllamaClient
from backend.app.services.qualitative import QualitativeService
from backend.app.services.rag import RagService
from backend.app.services.sec import SecService


MIN_CHUNKS = 5  # below this, we (re)index the ticker before summarizing


async def _ensure_company_row(rag: RagService, sec: SecService, ticker: str) -> str:
    """Resolve ticker -> company_id, inserting a companies row if missing."""
    upper = ticker.upper()
    rows = (
        rag.client.table("companies")
        .select("id")
        .eq("ticker", upper)
        .limit(1)
        .execute()
        .data
    )
    if rows:
        return rows[0]["id"]

    snapshot = await sec.resolve_company(upper)
    inserted = (
        rag.client.table("companies")
        .insert(
            {
                "ticker": snapshot.ticker,
                "company_name": snapshot.company_name,
                "cik": snapshot.cik,
            }
        )
        .execute()
        .data
    )
    return inserted[0]["id"]


def _chunk_count(rag: RagService, company_id: str) -> int:
    resp = (
        rag.client.table("filing_chunks")
        .select("id", count="exact")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    return resp.count or 0


def _indexed_accessions(rag: RagService, company_id: str) -> set[str]:
    rows = (
        rag.client.table("filing_chunks")
        .select("accession_number")
        .eq("company_id", company_id)
        .execute()
        .data
        or []
    )
    return {r["accession_number"] for r in rows}


async def _index_if_needed(
    rag: RagService, sec: SecService, ticker: str, company_id: str
) -> None:
    settings = get_settings()
    snapshot = await sec.resolve_company(ticker)
    filings, _ = await sec.fetch_recent_filings(snapshot.cik)
    target = (
        [f for f in filings if f.filing_type == "10-K"][:1]
        + [f for f in filings if f.filing_type == "10-Q"][:1]
        + [f for f in filings if f.filing_type == "8-K"][: settings.max_8k_per_ticker]
    )
    if not target:
        target = filings[:2]

    already = _indexed_accessions(rag, company_id)
    target = [f for f in target if f.accession_number not in already]
    if not target:
        print(f"  [skip-index] {ticker}: all target filings already indexed")
        return

    print(f"  [index] {ticker}: indexing {len(target)} new filing(s)")
    for filing in target:
        try:
            n = await rag.index_filing(company_id, filing)
            print(f"    {filing.filing_type} {filing.accession_number}: {n} chunks")
        except Exception as exc:
            print(f"    {filing.accession_number}: FAILED ({exc})")


async def _process(ticker: str) -> None:
    settings = get_settings()
    if not settings.has_supabase:
        print("ERROR: Supabase not configured. Check backend/.env.")
        sys.exit(1)
    if not settings.ollama_base_url:
        print("ERROR: OLLAMA_BASE_URL not configured. Check backend/.env.")
        sys.exit(1)

    rag = RagService(settings)
    sec = SecService(settings)
    ollama = OllamaClient(settings)
    svc = QualitativeService(settings, rag, ollama)

    print(f"\n=== {ticker.upper()} ===")
    company_id = await _ensure_company_row(rag, sec, ticker)
    await _index_if_needed(rag, sec, ticker.upper(), company_id)

    print(f"  [summarize] model={settings.ollama_model}")
    summary = await svc.summarize(ticker.upper())
    print(json.dumps(summary.model_dump(), indent=2, default=str))


def _safe_print(line: str) -> None:
    """Print a line, replacing any chars the active stdout encoding can't encode."""
    encoding = sys.stdout.encoding or "utf-8"
    sys.stdout.write(line.encode(encoding, errors="replace").decode(encoding) + "\n")


async def main(tickers: list[str]) -> None:
    for ticker in tickers:
        try:
            await _process(ticker)
        except Exception as exc:
            _safe_print(f"  [error] {ticker}: {exc}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m backend.scripts.smoke_index_and_summarize TICKER [TICKER ...]")
        sys.exit(1)
    asyncio.run(main([t.upper() for t in sys.argv[1:]]))
