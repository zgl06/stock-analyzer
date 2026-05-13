"""RAG service: chunk SEC filings, embed, store in Supabase pgvector, retrieve."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import httpx

from backend.app.config import Settings, get_settings
from backend.app.errors import NotFoundError, PersistenceError
from backend.app.models import FilingRecord
from backend.app.models.rag import RetrievedChunk
from backend.app.services._filing_text import html_to_text


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chunking policy constants
# ---------------------------------------------------------------------------
# Filing types ingested by this service (matches SEC service filter).
SUPPORTED_FILING_TYPES = {"10-K", "10-Q", "8-K"}

# Target chunk size in characters (~800 tokens at ~3.75 chars/token).
CHUNK_SIZE_CHARS = 3_000

# Overlap between consecutive chunks in characters.
CHUNK_OVERLAP_CHARS = 200

# ---------------------------------------------------------------------------
# Lazy embedding model loader
# ---------------------------------------------------------------------------
_embedding_model: Any = None  # SentenceTransformer instance, loaded on first use


def _get_embedding_model(settings: Settings | None = None) -> Any:
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer  # type: ignore[import]

        cfg = settings or get_settings()
        model_name = cfg.embedding_model_name
        logger.info("Loading embedding model %s", model_name)
        _embedding_model = SentenceTransformer(model_name)
    return _embedding_model


def _embed(texts: list[str], settings: Settings | None = None) -> list[list[float]]:
    model = _get_embedding_model(settings)
    vectors = model.encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vectors]


# ---------------------------------------------------------------------------
# Chunker
# ---------------------------------------------------------------------------

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE_CHARS, overlap: int = CHUNK_OVERLAP_CHARS) -> list[str]:
    """Split *text* into overlapping chunks of at most *chunk_size* chars.

    Uses sentence-boundary heuristics: tries to break at the nearest
    sentence end (. ! ?) before the hard limit to avoid cutting mid-sentence.
    """
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + chunk_size, length)

        # Prefer breaking at a sentence boundary within the last 20% of the window.
        if end < length:
            search_start = start + int(chunk_size * 0.8)
            segment = text[search_start:end]
            # Find the last sentence-ending punctuation followed by whitespace.
            match = None
            for m in re.finditer(r"[.!?]\s", segment):
                match = m
            if match:
                end = search_start + match.end()

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # If we consumed to the end of the text, stop.
        if end >= length:
            break

        next_start = end - overlap
        if next_start <= start:
            # Guard against infinite loop on pathological inputs.
            next_start = start + max(1, chunk_size // 2)
        start = next_start

    return chunks


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: chars / 4 (good enough for a budget check)."""
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# RagService
# ---------------------------------------------------------------------------

class RagService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: Any = None

    @property
    def client(self) -> Any:
        if self._client is None:
            if not self.settings.has_supabase:
                raise PersistenceError("Supabase is not configured.")
            # Lazy import so the module can be imported without supabase installed
            # (mirrors the pattern in storage.py).
            from supabase import create_client  # type: ignore[import]
            self._client = create_client(
                self.settings.supabase_url,
                self.settings.supabase_service_role_key,
            )
        return self._client

    # ------------------------------------------------------------------
    # Index a single filing
    # ------------------------------------------------------------------

    async def index_filing(
        self,
        company_id: str,
        filing: FilingRecord,
        *,
        refresh: bool = False,
    ) -> int:
        """Fetch, chunk, embed, and upsert a filing. Returns chunk count.

        Skips if rows already exist for *accession_number* unless *refresh=True*.
        Only processes SUPPORTED_FILING_TYPES; returns 0 for others.
        """
        if filing.filing_type not in SUPPORTED_FILING_TYPES:
            return 0

        if not filing.primary_document_url:
            logger.warning("Filing %s has no primary_document_url; skipping.", filing.accession_number)
            return 0

        if not refresh:
            existing = await asyncio.to_thread(self._chunk_count_for_accession, filing.accession_number)
            if existing > 0:
                logger.debug("Filing %s already indexed (%d chunks); skipping.", filing.accession_number, existing)
                return existing

        # Fetch HTML.
        html = await self._fetch_html(filing.primary_document_url)
        text = html_to_text(html)
        chunks = chunk_text(text)

        if not chunks:
            logger.warning("Filing %s produced no chunks after stripping.", filing.accession_number)
            return 0

        # Embed all chunks in one batch (CPU-bound; run in thread).
        embeddings = await asyncio.to_thread(_embed, chunks, self.settings)

        # Build rows.
        rows = []
        filing_date_str = filing.filing_date.isoformat() if hasattr(filing.filing_date, "isoformat") else str(filing.filing_date)
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            rows.append({
                "company_id": company_id,
                "accession_number": filing.accession_number,
                "filing_type": filing.filing_type,
                "filing_date": filing_date_str,
                "chunk_index": idx,
                "text": chunk,
                "embedding": embedding,
                "token_count": _estimate_tokens(chunk),
            })

        # If refreshing, delete existing chunks first.
        if refresh:
            await asyncio.to_thread(self._delete_chunks_for_accession, filing.accession_number)

        await asyncio.to_thread(self._upsert_chunks, rows)
        logger.info("Indexed %d chunks for filing %s.", len(rows), filing.accession_number)
        return len(rows)

    # ------------------------------------------------------------------
    # Retrieve top-k chunks
    # ------------------------------------------------------------------

    async def retrieve(
        self,
        ticker: str,
        query: str,
        *,
        k: int = 6,
        max_tokens: int = 3_000,
        min_score: float = 0.2,
    ) -> list[RetrievedChunk]:
        """Embed *query*, run cosine similarity search, return top-k chunks.

        Resolves company_id from the *companies* table by ticker.
        Applies *min_score* filter and *max_tokens* budget cap (cumulative).
        Results are returned in descending similarity order.
        """
        company_id = await asyncio.to_thread(self._resolve_company_id, ticker)

        query_embedding = await asyncio.to_thread(_embed, [query], self.settings)
        vector = query_embedding[0]

        raw_rows = await asyncio.to_thread(
            self._rpc_match_chunks,
            vector,
            k,
            company_id,
        )

        results: list[RetrievedChunk] = []
        cumulative_tokens = 0
        for row in raw_rows:
            score = float(row.get("score", 0.0))
            if score < min_score:
                continue
            token_count = int(row.get("token_count", 0))
            if cumulative_tokens + token_count > max_tokens:
                break
            results.append(
                RetrievedChunk(
                    chunk_id=str(row["id"]),
                    accession_number=row["accession_number"],
                    filing_type=row["filing_type"],
                    filing_date=row["filing_date"],
                    text=row["text"],
                    score=score,
                    token_count=token_count,
                )
            )
            cumulative_tokens += token_count

        return results

    # ------------------------------------------------------------------
    # Supabase helpers (all sync — called via asyncio.to_thread)
    # ------------------------------------------------------------------

    def _resolve_company_id(self, ticker: str) -> str:
        response = (
            self.client.table("companies")
            .select("id")
            .eq("ticker", ticker.upper())
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            raise NotFoundError(f"No company stored for ticker '{ticker}'.")
        return rows[0]["id"]

    def _chunk_count_for_accession(self, accession_number: str) -> int:
        response = (
            self.client.table("filing_chunks")
            .select("id", count="exact")
            .eq("accession_number", accession_number)
            .execute()
        )
        return response.count or 0

    def _delete_chunks_for_accession(self, accession_number: str) -> None:
        self.client.table("filing_chunks").delete().eq("accession_number", accession_number).execute()

    def _upsert_chunks(self, rows: list[dict]) -> None:
        # Insert in batches of 100 to stay within Supabase request limits.
        batch_size = 100
        for i in range(0, len(rows), batch_size):
            self.client.table("filing_chunks").insert(rows[i : i + batch_size]).execute()

    def _rpc_match_chunks(
        self,
        query_embedding: list[float],
        match_count: int,
        company_id: str,
    ) -> list[dict]:
        response = self.client.rpc(
            "match_filing_chunks",
            {
                "query_embedding": query_embedding,
                "match_count": match_count,
                "p_company_id": company_id,
            },
        ).execute()
        return response.data or []

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------

    async def _fetch_html(self, url: str) -> str:
        headers = {
            "User-Agent": self.settings.sec_user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "text/html,application/xhtml+xml,*/*",
        }
        timeout = httpx.Timeout(30.0, connect=10.0)
        async with httpx.AsyncClient(headers=headers, timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
        return response.text
