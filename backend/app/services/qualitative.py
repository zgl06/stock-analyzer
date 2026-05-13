"""L2 Qualitative summary service.

Orchestrates: RAG retrieval -> prompt build -> Ollama call -> validation/retry
-> number-guard -> DocumentSummary.

Design decisions
----------------
- Fixed multi-intent query for v1: "financial performance, risk factors,
  guidance, business outlook".  A single query covers the four most common
  reasons an analyst reads a filing.  Phase L3 or L4 can introduce per-intent
  retrieval if needed.
- Validate-then-retry: one LLM call, one retry on ValidationError, then raise.
  Two attempts is sufficient for transient schema drift; more retries add
  latency without proportional benefit for a structured-output task.
- Number guard: applied as post-processing.  The prompt is the primary defence;
  the regex strip is a second safety net for numbers the model hallucinates
  despite the instruction.  Trade-off: the regex can over-redact if a number
  that looks fabricated is actually derived from the chunk text in a non-obvious
  way (e.g. "revenue doubled to $X" where $X is computed, not quoted).  We
  accept this false-positive risk because hallucinated numbers are more harmful
  than a conservative redaction.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import ValidationError

from backend.app.config import Settings
from backend.app.errors import LLMError, NotFoundError
from backend.app.models.document_summary import DocumentSummary
from backend.app.models.rag import RetrievedChunk
from backend.app.services._qual_prompts import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)
from backend.app.services.ollama_client import OllamaClient
from backend.app.services.rag import RagService


logger = logging.getLogger(__name__)

QUALITATIVE_TTL_HOURS = 24

# Multi-query retrieval: a single broad query was pulling risk-factor and
# SOX/audit boilerplate over and over, starving the LLM of MD&A and guidance
# text. We fan out four targeted queries and merge by best score per chunk.
_RETRIEVAL_QUERIES = (
    # Broad catch-all (originally the v1 single query). Empirically the only
    # query that reliably surfaces the headline revenue/EPS/growth chunks for
    # tickers like NVDA — narrow targeted queries kept missing them.
    "financial performance, risk factors, guidance, business outlook",
    "management discussion of results of operations and outlook",
    "we expect anticipate believe full year fiscal outlook revenue margin",
    "forward looking statements guidance reaffirm raise lower withdraw",
    "revenue growth drivers segment performance year over year",
    "key risk factors and uncertainties affecting business",
    "government investment funding grant CHIPS Act subsidy equity stake",
    "strategic partnership joint venture foundry deal customer agreement acquisition divestiture",
)

# Per-query top-k. With 5 queries x 4 chunks and dedup, we typically end up
# with 10-16 unique chunks, which we then trim to the caller's k.
_PER_QUERY_K = 4

# Chunks whose text is dominated by SOX / audit / disclosure-controls
# boilerplate add no analytical value. We down-rank by dropping them outright
# before merging — these phrases are highly specific to that genre and almost
# never appear in MD&A or guidance prose.
_BOILERPLATE_RE = re.compile(
    r"internal control over financial reporting"
    r"|sarbanes-oxley"
    r"|disclosure controls and procedures"
    r"|disclosure controls.{0,40}effective"
    r"|attestation report"
    r"|pcaob"
    r"|principal executive officer and principal financial officer"
    r"|maintained effective"
    r"|fairly presented.{0,40}material respects"
    r"|in conformity with (u\.s\.|generally accepted) accounting principles",
    re.IGNORECASE,
)

# Regex matching numeric tokens that might be hallucinated (e.g. 12%, $1.5B,
# 47.3%, 2,500, 0.83).  We look for optional $ then digits with optional
# comma-separators / decimal part / trailing %.
# Note: we strip trailing commas from matches during collection so that
# "2024," in a chunk and "2024" in the thesis compare as equal.
_NUMBER_RE = re.compile(r"\$?\d[\d,]*\.?\d*%?")

# Thin-evidence thesis shown when there are not enough chunks to form a view.
_THIN_THESIS = "Insufficient filings retrieved to form a grounded view."


class QualitativeService:
    def __init__(
        self,
        settings: Settings,
        rag_service: RagService,
        ollama_client: OllamaClient,
    ) -> None:
        self._settings = settings
        self._rag = rag_service
        self._ollama = ollama_client
        self._client: Any = None

    # ------------------------------------------------------------------
    # Supabase client (lazy, mirrors RagService pattern)
    # ------------------------------------------------------------------

    @property
    def client(self) -> Any:
        if self._client is None:
            if not self._settings.has_supabase:
                from backend.app.errors import PersistenceError
                raise PersistenceError("Supabase is not configured.")
            from supabase import create_client  # type: ignore[import]
            self._client = create_client(
                self._settings.supabase_url,
                self._settings.supabase_service_role_key,
            )
        return self._client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_cached(self, ticker: str) -> DocumentSummary | None:
        """Return a cached DocumentSummary if one exists and is within TTL, else None."""
        try:
            company_resp = (
                self.client.table("companies")
                .select("id")
                .eq("ticker", ticker.upper())
                .limit(1)
                .execute()
            )
            rows = company_resp.data or []
            if not rows:
                return None
            company_id = rows[0]["id"]

            summary_resp = (
                self.client.table("document_summaries")
                .select("payload, created_at")
                .eq("company_id", company_id)
                .eq("prompt_version", PROMPT_VERSION)
                .eq("model_name", self._settings.ollama_model)
                .limit(1)
                .execute()
            )
            summary_rows = summary_resp.data or []
            if not summary_rows:
                return None

            row = summary_rows[0]
            created_at_raw = row["created_at"]
            if isinstance(created_at_raw, str):
                created_at = datetime.fromisoformat(
                    created_at_raw.replace("Z", "+00:00")
                )
            else:
                created_at = created_at_raw
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)

            cutoff = datetime.now(timezone.utc) - timedelta(hours=QUALITATIVE_TTL_HOURS)
            if created_at < cutoff:
                logger.debug("Cached qualitative summary for %s is expired.", ticker)
                return None

            return DocumentSummary.model_validate(row["payload"])
        except Exception as exc:
            logger.warning("get_cached failed for %s: %s", ticker, exc)
            return None

    def _persist(self, company_id: str, summary: DocumentSummary) -> None:
        """Upsert the summary into document_summaries."""
        try:
            self.client.table("document_summaries").upsert(
                {
                    "company_id": company_id,
                    "prompt_version": summary.prompt_version,
                    "model_name": summary.model_name,
                    "payload": summary.model_dump(mode="json"),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
                on_conflict="company_id,prompt_version,model_name",
            ).execute()
        except Exception as exc:
            logger.warning("Failed to persist qualitative summary: %s", exc)

    def _resolve_company_id(self, ticker: str) -> str | None:
        try:
            resp = (
                self.client.table("companies")
                .select("id")
                .eq("ticker", ticker.upper())
                .limit(1)
                .execute()
            )
            rows = resp.data or []
            return rows[0]["id"] if rows else None
        except Exception as exc:
            logger.warning("Could not resolve company_id for %s: %s", ticker, exc)
            return None

    async def summarize(
        self,
        ticker: str,
        *,
        k: int = 6,
        facts: dict[str, Any] | None = None,
    ) -> DocumentSummary:
        """Produce a DocumentSummary for *ticker*.

        Steps
        -----
        1. Check Supabase cache (if Supabase configured); return hit if fresh.
        2. Retrieve up to *k* chunks via RagService.
        3. Short-circuit to a thin-evidence stub if <2 chunks returned.
        4. Build prompts and call Ollama with format=json.
        5. Validate against DocumentSummary; retry once on ValidationError.
        6. Overwrite service-managed fields (prompt_version, model_name,
           chunk_ids, disclaimer).
        7. Strip invented numbers from thesis/positives/risks.
        8. Persist result to Supabase cache.
        """
        if self._settings.has_supabase:
            cached = self.get_cached(ticker)
            if cached is not None:
                logger.debug("Returning cached qualitative summary for %s.", ticker)
                return cached

        chunks = await self._multi_query_retrieve(ticker, k=k)

        if len(chunks) < 2:
            logger.info(
                "Thin evidence for %s (%d chunks); returning stub summary.",
                ticker,
                len(chunks),
            )
            return self._thin_evidence_stub(chunks)

        system = SYSTEM_PROMPT
        user = build_user_prompt(ticker, chunks, facts=facts)

        raw = await self._call_with_retry(system, user)

        summary = self._stamp_service_fields(raw, chunks)
        summary = self._apply_number_guard(summary, chunks, facts)

        if self._settings.has_supabase:
            company_id = self._resolve_company_id(ticker)
            if company_id:
                self._persist(company_id, summary)

        return summary

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _multi_query_retrieve(
        self, ticker: str, *, k: int
    ) -> list[RetrievedChunk]:
        """Fan out targeted retrieval queries, drop boilerplate, dedup by chunk_id.

        Keeps the highest-scoring occurrence of each chunk across queries, then
        returns the top *k* by score.
        """
        best: dict[str, RetrievedChunk] = {}
        for query in _RETRIEVAL_QUERIES:
            try:
                hits = await self._rag.retrieve(ticker, query, k=_PER_QUERY_K)
            except Exception as exc:
                logger.warning("Retrieval failed for query %r: %s", query, exc)
                continue
            for hit in hits:
                if _BOILERPLATE_RE.search(hit.text):
                    continue
                prior = best.get(hit.chunk_id)
                if prior is None or hit.score > prior.score:
                    best[hit.chunk_id] = hit

        merged = sorted(best.values(), key=lambda c: c.score, reverse=True)
        return merged[:k]

    def _thin_evidence_stub(self, chunks: list[RetrievedChunk]) -> DocumentSummary:
        """Return a safe stub when retrieval found fewer than 2 chunks."""
        return DocumentSummary(
            tone="neutral",
            thesis=_THIN_THESIS,
            positives=[
                "Insufficient data to identify positives.",
                "Please ensure filings are indexed for this ticker.",
            ],
            risks=[
                "Insufficient data to assess risks.",
                "Retrieval returned fewer than 2 relevant chunks.",
            ],
            guidance_flavor="none_mentioned",
            evidence_quality="thin",
            prompt_version=PROMPT_VERSION,
            model_name=self._settings.ollama_model,
            chunk_ids=[c.chunk_id for c in chunks],
        )

    async def _call_with_retry(self, system: str, user: str) -> DocumentSummary:
        """Call Ollama, validate, retry once on ValidationError, then raise."""
        raw1 = await self._ollama.generate_json(system=system, user=user)
        raw1 = _normalize_payload(_unwrap_envelope(raw1))
        try:
            return DocumentSummary.model_validate(raw1)
        except ValidationError as first_err:
            logger.warning(
                "First Ollama response failed DocumentSummary validation: %s",
                _short_validation_msg(first_err),
            )
            retry_user = (
                user
                + "\n\nYour previous reply was invalid. Reply ONLY with a flat "
                "JSON object whose top-level keys are exactly: tone, thesis, "
                "positives, risks, guidance_flavor, evidence_quality. No "
                "envelope keys, no wrapper, no markdown."
            )
            raw2 = await self._ollama.generate_json(system=system, user=retry_user)
            raw2 = _normalize_payload(_unwrap_envelope(raw2))
            try:
                return DocumentSummary.model_validate(raw2)
            except ValidationError as second_err:
                raise LLMError(
                    f"Qualitative summary unavailable: two consecutive Ollama "
                    f"responses failed validation. Last error: {second_err}"
                ) from second_err

    def _stamp_service_fields(
        self,
        summary: DocumentSummary,
        chunks: list[RetrievedChunk],
    ) -> DocumentSummary:
        """Overwrite the service-managed fields regardless of what the model emitted."""
        # model_copy(update=...) returns a new instance with updated fields.
        return summary.model_copy(
            update={
                "prompt_version": PROMPT_VERSION,
                "model_name": self._settings.ollama_model,
                "chunk_ids": [c.chunk_id for c in chunks],
            }
        )

    def _apply_number_guard(
        self,
        summary: DocumentSummary,
        chunks: list[RetrievedChunk],
        facts: dict[str, Any] | None,
    ) -> DocumentSummary:
        """Strip numeric tokens from thesis/positives/risks not found in source material.

        The allowed set is: every number token found in any retrieved chunk text
        plus every number token found in the facts dict values (as strings).

        Trade-off: we use a sentence-level replacement (replace the surrounding
        sentence with [number redacted]) to preserve readability.  A word-level
        deletion would leave grammatically broken text.
        """
        allowed = _collect_allowed_numbers(chunks, facts)

        thesis = _strip_invented_numbers(summary.thesis, allowed)
        positives = [_strip_invented_numbers(b, allowed) for b in summary.positives]
        risks = [_strip_invented_numbers(b, allowed) for b in summary.risks]

        return summary.model_copy(
            update={
                "thesis": thesis,
                "positives": positives,
                "risks": risks,
            }
        )


# ---------------------------------------------------------------------------
# Number-guard utilities (module-level for easy unit testing)
# ---------------------------------------------------------------------------


def _collect_allowed_numbers(
    chunks: list[RetrievedChunk],
    facts: dict[str, Any] | None,
) -> frozenset[str]:
    """Return the set of number tokens present in the source material.

    Trailing commas are stripped from each match so that "2024," found in a
    chunk and "2024" produced by the model compare as equal.
    """
    tokens: set[str] = set()
    for chunk in chunks:
        tokens.update(m.rstrip(",") for m in _NUMBER_RE.findall(chunk.text))
    if facts:
        for value in facts.values():
            tokens.update(m.rstrip(",") for m in _NUMBER_RE.findall(str(value)))
    return frozenset(tokens)


_REQUIRED_KEYS = {"tone", "thesis", "positives", "risks", "guidance_flavor", "evidence_quality"}


def _unwrap_envelope(raw: Any, depth: int = 0) -> Any:
    """Unwrap nested wrappers like {"systemResponse": {"jsonObject": {...}}}.

    Some Ollama models (qwen2.5:7b in particular) wrap the requested JSON in
    one or two levels of generic envelope keys despite the prompt asking for
    a flat object. We do a bounded DFS through nested dict values and return
    the first dict that contains our required schema keys. Falls back to the
    original payload if no match is found.
    """
    if not isinstance(raw, dict):
        return raw
    if _REQUIRED_KEYS.issubset(raw.keys()):
        return raw
    if depth > 4:
        return raw
    for value in raw.values():
        if isinstance(value, dict):
            unwrapped = _unwrap_envelope(value, depth + 1)
            if isinstance(unwrapped, dict) and _REQUIRED_KEYS.issubset(unwrapped.keys()):
                return unwrapped
    return raw


# Allowed enum values mirrored from DocumentSummary. When the model emits an
# empty string, an unknown synonym, or anything else broken, we coerce to a
# safe default so validation can still pass.
_TONE_VALUES = {"positive", "neutral", "cautious", "negative", "mixed"}
_GUIDANCE_VALUES = {"raised", "reaffirmed", "lowered", "withdrawn", "none_mentioned"}
_EVIDENCE_VALUES = {"strong", "moderate", "thin"}

_TONE_SYNONYMS = {
    "bullish": "positive",
    "optimistic": "positive",
    "bearish": "negative",
    "pessimistic": "negative",
    "concerned": "cautious",
    "cautionary": "cautious",
    "neutral/mixed": "mixed",
    "mixed/neutral": "mixed",
    "balanced": "mixed",
}
_GUIDANCE_SYNONYMS = {
    "raise": "raised",
    "increased": "raised",
    "reaffirm": "reaffirmed",
    "maintained": "reaffirmed",
    "unchanged": "reaffirmed",
    "lower": "lowered",
    "reduced": "lowered",
    "cut": "lowered",
    "withdraw": "withdrawn",
    "none": "none_mentioned",
    "not mentioned": "none_mentioned",
    "n/a": "none_mentioned",
    "": "none_mentioned",
}
_EVIDENCE_SYNONYMS = {
    "weak": "thin",
    "limited": "thin",
    "sparse": "thin",
    "medium": "moderate",
    "average": "moderate",
    "high": "strong",
    "robust": "strong",
}

# Fields the service stamps unconditionally; safe to discard from the LLM
# payload before validation so they never trigger extra="forbid" errors.
_SERVICE_MANAGED_FIELDS = {"prompt_version", "model_name", "chunk_ids", "disclaimer"}

_ALLOWED_KEYS = _REQUIRED_KEYS | _SERVICE_MANAGED_FIELDS


def _coerce_enum(value: Any, allowed: set[str], synonyms: dict[str, str], default: str) -> str:
    """Map a model-emitted enum-ish value to one of *allowed*, else *default*."""
    if not isinstance(value, str):
        return default
    cleaned = value.strip().lower()
    if cleaned in allowed:
        return cleaned
    if cleaned in synonyms:
        return synonyms[cleaned]
    if not cleaned:
        return default
    return default


def _coerce_bullet_list(value: Any) -> list[str]:
    """Best-effort conversion of a model-emitted bullets field to a list[str].

    Handles three observed broken shapes:
    - JSON-array-as-string: "[\"a\", \"b\"]"
    - Newline/bullet separated string: "- a\n- b"
    - Single string with no separators: returned as a one-element list.
    Returns [] for anything that cannot be salvaged; the schema validator will
    then surface a helpful error.
    """
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except (ValueError, TypeError):
                pass
        lines = [
            re.sub(r"^[\s\-\*•\d\.\)]+", "", line).strip()
            for line in text.splitlines()
            if line.strip()
        ]
        lines = [line for line in lines if line]
        if len(lines) >= 2:
            return lines
        return [text]
    return []


def _normalize_payload(raw: Any) -> Any:
    """Coerce a near-valid LLM payload into a shape DocumentSummary will accept.

    Only mutates known fields; anything we do not understand is dropped so
    the model's extra="forbid" check does not reject the whole response.
    Service-stamped fields are dropped here and re-applied later by
    _stamp_service_fields, so any garbage the model emits for them is harmless.
    """
    if not isinstance(raw, dict):
        return raw

    out: dict[str, Any] = {k: v for k, v in raw.items() if k in _ALLOWED_KEYS}

    # Replace service-stamped fields with placeholders; whatever the model
    # emits here is discarded and _stamp_service_fields overwrites them after
    # validation. Placeholders ensure the required fields are present so
    # DocumentSummary validation does not fail just because the LLM omitted them.
    out["prompt_version"] = "pending"
    out["model_name"] = "pending"
    out["chunk_ids"] = []
    out.pop("disclaimer", None)

    if "tone" in out:
        out["tone"] = _coerce_enum(out["tone"], _TONE_VALUES, _TONE_SYNONYMS, "neutral")
    if "guidance_flavor" in out:
        out["guidance_flavor"] = _coerce_enum(
            out["guidance_flavor"], _GUIDANCE_VALUES, _GUIDANCE_SYNONYMS, "none_mentioned"
        )
    if "evidence_quality" in out:
        out["evidence_quality"] = _coerce_enum(
            out["evidence_quality"], _EVIDENCE_VALUES, _EVIDENCE_SYNONYMS, "thin"
        )
    if "positives" in out:
        out["positives"] = _coerce_bullet_list(out["positives"])[:5]
    if "risks" in out:
        out["risks"] = _coerce_bullet_list(out["risks"])[:5]
    if "thesis" in out and not isinstance(out["thesis"], str):
        out["thesis"] = str(out["thesis"]) if out["thesis"] is not None else ""

    return out


def _short_validation_msg(err: ValidationError) -> str:
    """Compact one-line summary of a ValidationError for logging."""
    parts = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in err.errors()]
    return "; ".join(parts[:5])


def _strip_invented_numbers(text: str, allowed_tokens: frozenset[str]) -> str:
    """Replace sentences containing a fabricated number with '[number redacted]'.

    A number is considered fabricated if it matches _NUMBER_RE and does NOT
    appear in *allowed_tokens*.

    We operate at sentence granularity (split on '. ') because replacing only
    the digit token typically leaves grammatically incomplete fragments.
    """
    sentences = re.split(r"(?<=[.!?])\s+", text)
    cleaned: list[str] = []
    for sentence in sentences:
        found_numbers = _NUMBER_RE.findall(sentence)
        fabricated = [n for n in found_numbers if n.rstrip(",") not in allowed_tokens]
        if fabricated:
            cleaned.append("[number redacted]")
        else:
            cleaned.append(sentence)
    return " ".join(cleaned)
