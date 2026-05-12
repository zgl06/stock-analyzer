"""Tests for the L2 QualitativeService and DocumentSummary schema.

Mocks both RagService.retrieve and OllamaClient.generate_json so no live
Ollama instance or Supabase connection is required.
"""

from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import ValidationError

from backend.app.config import Settings
from backend.app.errors import LLMError
from backend.app.models.document_summary import DocumentSummary
from backend.app.models.rag import RetrievedChunk
from backend.app.services._qual_prompts import PROMPT_VERSION
from backend.app.services.qualitative import (
    QualitativeService,
    _collect_allowed_numbers,
    _normalize_payload,
    _strip_invented_numbers,
    _unwrap_envelope,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_settings() -> Settings:
    return Settings(
        ollama_base_url="http://localhost:11434",
        ollama_model="qwen2.5:7b",
    )


def _make_chunk(
    chunk_id: str = "c1",
    text: str = "Operating margin expanded as cost discipline improved.",
    score: float = 0.85,
    filing_type: str = "10-K",
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        accession_number="0000000000-24-000001",
        filing_type=filing_type,
        filing_date=date(2024, 1, 15),
        text=text,
        score=score,
        token_count=10,
    )


def _valid_llm_payload() -> dict:
    """Minimal valid payload the LLM should return (service stamps the rest)."""
    return {
        "tone": "positive",
        "thesis": "The company demonstrated solid execution with margin expansion.",
        "positives": [
            "Operating leverage improved quarter-over-quarter.",
            "Management expressed confidence in near-term demand.",
        ],
        "risks": [
            "Macro uncertainty could pressure discretionary spend.",
            "Supply chain disruptions remain a watchlist item.",
        ],
        "guidance_flavor": "reaffirmed",
        "evidence_quality": "moderate",
        # Service-stamped fields — model should not emit these, but if it does
        # they must be accepted and then overwritten by the service.
        "prompt_version": "wrong-version",
        "model_name": "wrong-model",
        "chunk_ids": [],
    }


# ---------------------------------------------------------------------------
# a) Happy path
# ---------------------------------------------------------------------------

class HappyPathTests(unittest.IsolatedAsyncioTestCase):
    async def test_happy_path_returns_populated_summary(self) -> None:
        settings = _make_settings()
        chunks = [_make_chunk("c1"), _make_chunk("c2")]

        rag = MagicMock()
        rag.retrieve = AsyncMock(return_value=chunks)

        ollama = MagicMock()
        ollama.generate_json = AsyncMock(return_value=_valid_llm_payload())

        svc = QualitativeService(settings, rag, ollama)
        result = await svc.summarize("AAPL")

        self.assertIsInstance(result, DocumentSummary)
        self.assertEqual(result.prompt_version, PROMPT_VERSION)
        self.assertEqual(result.model_name, settings.ollama_model)
        self.assertEqual(result.chunk_ids, ["c1", "c2"])
        self.assertEqual(result.tone, "positive")
        self.assertGreater(len(result.positives), 0)
        self.assertGreater(len(result.risks), 0)

    async def test_disclaimer_is_locked(self) -> None:
        settings = _make_settings()
        chunks = [_make_chunk("c1"), _make_chunk("c2")]

        rag = MagicMock()
        rag.retrieve = AsyncMock(return_value=chunks)

        payload = _valid_llm_payload()
        payload["disclaimer"] = "Totally custom disclaimer."
        ollama = MagicMock()
        ollama.generate_json = AsyncMock(return_value=payload)

        svc = QualitativeService(settings, rag, ollama)
        result = await svc.summarize("AAPL")

        self.assertIn("Not investment advice", result.disclaimer)


# ---------------------------------------------------------------------------
# b) Thin evidence short-circuit
# ---------------------------------------------------------------------------

class ThinEvidenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_zero_chunks_returns_thin_without_llm(self) -> None:
        settings = _make_settings()

        rag = MagicMock()
        rag.retrieve = AsyncMock(return_value=[])

        ollama = MagicMock()
        ollama.generate_json = AsyncMock()

        svc = QualitativeService(settings, rag, ollama)
        result = await svc.summarize("XYZ")

        self.assertEqual(result.evidence_quality, "thin")
        ollama.generate_json.assert_not_called()

    async def test_one_chunk_returns_thin_without_llm(self) -> None:
        settings = _make_settings()

        rag = MagicMock()
        rag.retrieve = AsyncMock(return_value=[_make_chunk("c1")])

        ollama = MagicMock()
        ollama.generate_json = AsyncMock()

        svc = QualitativeService(settings, rag, ollama)
        result = await svc.summarize("XYZ")

        self.assertEqual(result.evidence_quality, "thin")
        ollama.generate_json.assert_not_called()

    async def test_thin_stub_has_correct_service_fields(self) -> None:
        settings = _make_settings()

        rag = MagicMock()
        rag.retrieve = AsyncMock(return_value=[_make_chunk("c99")])

        ollama = MagicMock()
        ollama.generate_json = AsyncMock()

        svc = QualitativeService(settings, rag, ollama)
        result = await svc.summarize("XYZ")

        self.assertEqual(result.prompt_version, PROMPT_VERSION)
        self.assertEqual(result.model_name, settings.ollama_model)
        self.assertEqual(result.chunk_ids, ["c99"])


# ---------------------------------------------------------------------------
# c) Validation retry
# ---------------------------------------------------------------------------

class ValidationRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_retry_on_first_invalid_returns_second_valid(self) -> None:
        settings = _make_settings()
        chunks = [_make_chunk("c1"), _make_chunk("c2")]

        rag = MagicMock()
        rag.retrieve = AsyncMock(return_value=chunks)

        # First call: missing required fields -> pydantic will reject.
        bad_payload = {"tone": "positive"}  # missing thesis, positives, etc.
        good_payload = _valid_llm_payload()

        ollama = MagicMock()
        ollama.generate_json = AsyncMock(side_effect=[bad_payload, good_payload])

        svc = QualitativeService(settings, rag, ollama)
        result = await svc.summarize("MSFT")

        self.assertEqual(ollama.generate_json.call_count, 2)
        self.assertIsInstance(result, DocumentSummary)
        self.assertEqual(result.tone, "positive")


# ---------------------------------------------------------------------------
# d) Hard failure — both attempts invalid
# ---------------------------------------------------------------------------

class HardFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_both_attempts_invalid_raises_llm_error(self) -> None:
        settings = _make_settings()
        chunks = [_make_chunk("c1"), _make_chunk("c2")]

        rag = MagicMock()
        rag.retrieve = AsyncMock(return_value=chunks)

        bad = {"tone": "positive"}  # always missing required fields
        ollama = MagicMock()
        ollama.generate_json = AsyncMock(side_effect=[bad, bad])

        svc = QualitativeService(settings, rag, ollama)

        with self.assertRaises(LLMError):
            await svc.summarize("TSLA")

        self.assertEqual(ollama.generate_json.call_count, 2)


# ---------------------------------------------------------------------------
# e) No invented numbers
# ---------------------------------------------------------------------------

class NoInventedNumbersTests(unittest.IsolatedAsyncioTestCase):
    async def test_invented_number_removed_from_thesis(self) -> None:
        """A number absent from chunks/facts must be stripped from the output."""
        settings = _make_settings()
        # Chunks contain no numbers.
        chunks = [
            _make_chunk("c1", text="The company maintained its market position."),
            _make_chunk("c2", text="Management noted operational efficiency gains."),
        ]

        rag = MagicMock()
        rag.retrieve = AsyncMock(return_value=chunks)

        # LLM fabricates "47.3%" which is not in any chunk text.
        payload = _valid_llm_payload()
        payload["thesis"] = "Revenue grew 47.3% YoY driven by strong demand."
        payload["positives"] = [
            "Operating margin expanded as cost discipline improved.",
            "Management expressed confidence in near-term demand.",
        ]
        payload["risks"] = [
            "Macro uncertainty could pressure discretionary spend.",
            "Supply chain disruptions remain a watchlist item.",
        ]

        ollama = MagicMock()
        ollama.generate_json = AsyncMock(return_value=payload)

        svc = QualitativeService(settings, rag, ollama)
        result = await svc.summarize("NVDA")

        self.assertNotIn("47.3%", result.thesis)

    async def test_invented_number_removed_from_positives(self) -> None:
        settings = _make_settings()
        chunks = [
            _make_chunk("c1", text="Strong product adoption reported."),
            _make_chunk("c2", text="Operational discipline highlighted."),
        ]

        rag = MagicMock()
        rag.retrieve = AsyncMock(return_value=chunks)

        payload = _valid_llm_payload()
        payload["positives"] = [
            "EPS beat by $0.45 versus consensus.",   # $0.45 is fabricated
            "Management expressed confidence in near-term demand.",
        ]

        ollama = MagicMock()
        ollama.generate_json = AsyncMock(return_value=payload)

        svc = QualitativeService(settings, rag, ollama)
        result = await svc.summarize("NVDA")

        self.assertNotIn("$0.45", " ".join(result.positives))


# ---------------------------------------------------------------------------
# f) Allowed numbers pass through
# ---------------------------------------------------------------------------

class AllowedNumbersTests(unittest.IsolatedAsyncioTestCase):
    async def test_number_present_in_chunk_survives(self) -> None:
        settings = _make_settings()
        chunks = [
            _make_chunk("c1", text="Revenue grew 12% in 2024, ahead of the prior year."),
            _make_chunk("c2", text="Management noted operational efficiency gains."),
        ]

        rag = MagicMock()
        rag.retrieve = AsyncMock(return_value=chunks)

        payload = _valid_llm_payload()
        payload["thesis"] = "Revenue grew 12% in 2024 reflecting strong demand."

        ollama = MagicMock()
        ollama.generate_json = AsyncMock(return_value=payload)

        svc = QualitativeService(settings, rag, ollama)
        result = await svc.summarize("AAPL")

        self.assertIn("12%", result.thesis)

    async def test_number_in_facts_survives(self) -> None:
        settings = _make_settings()
        chunks = [
            _make_chunk("c1", text="Strong product adoption reported."),
            _make_chunk("c2", text="Operational discipline highlighted."),
        ]

        rag = MagicMock()
        rag.retrieve = AsyncMock(return_value=chunks)

        payload = _valid_llm_payload()
        payload["thesis"] = "The company has approximately 15500 employees."

        ollama = MagicMock()
        ollama.generate_json = AsyncMock(return_value=payload)

        svc = QualitativeService(settings, rag, ollama)
        # "15500" is injected as a validated fact.
        result = await svc.summarize("AAPL", facts={"employee_count": "15500"})

        self.assertIn("15500", result.thesis)


# ---------------------------------------------------------------------------
# g) Schema bounds
# ---------------------------------------------------------------------------

class SchemaBoundsTests(unittest.TestCase):
    def _base_kwargs(self) -> dict:
        return {
            "tone": "neutral",
            "thesis": "A reasonably descriptive thesis sentence.",
            "positives": ["Positive one.", "Positive two."],
            "risks": ["Risk one.", "Risk two."],
            "guidance_flavor": "none_mentioned",
            "evidence_quality": "moderate",
            "prompt_version": PROMPT_VERSION,
            "model_name": "qwen2.5:7b",
            "chunk_ids": [],
        }

    def test_too_many_positives_raises(self) -> None:
        kwargs = self._base_kwargs()
        kwargs["positives"] = [f"Item {i}" for i in range(6)]
        with self.assertRaises(ValidationError):
            DocumentSummary(**kwargs)

    def test_too_many_risks_raises(self) -> None:
        kwargs = self._base_kwargs()
        kwargs["risks"] = [f"Risk {i}" for i in range(6)]
        with self.assertRaises(ValidationError):
            DocumentSummary(**kwargs)

    def test_too_few_positives_raises(self) -> None:
        kwargs = self._base_kwargs()
        kwargs["positives"] = ["Only one item."]
        with self.assertRaises(ValidationError):
            DocumentSummary(**kwargs)

    def test_thesis_too_long_raises(self) -> None:
        kwargs = self._base_kwargs()
        kwargs["thesis"] = "x" * 601
        with self.assertRaises(ValidationError):
            DocumentSummary(**kwargs)

    def test_bullet_too_long_raises(self) -> None:
        kwargs = self._base_kwargs()
        kwargs["positives"] = ["x" * 241, "Short item."]
        with self.assertRaises(ValidationError):
            DocumentSummary(**kwargs)

    def test_valid_five_items_accepted(self) -> None:
        kwargs = self._base_kwargs()
        kwargs["positives"] = [f"Item {i}" for i in range(5)]
        kwargs["risks"] = [f"Risk {i}" for i in range(5)]
        result = DocumentSummary(**kwargs)
        self.assertEqual(len(result.positives), 5)


# ---------------------------------------------------------------------------
# Unit tests for number-guard helpers
# ---------------------------------------------------------------------------

class StripInventedNumbersTests(unittest.TestCase):
    def test_fabricated_number_replaced(self) -> None:
        allowed: frozenset[str] = frozenset()
        result = _strip_invented_numbers("Revenue grew 47.3% YoY.", allowed)
        self.assertNotIn("47.3%", result)
        self.assertIn("[number redacted]", result)

    def test_allowed_number_preserved(self) -> None:
        allowed: frozenset[str] = frozenset(["12%"])
        result = _strip_invented_numbers("Revenue grew 12% in the period.", allowed)
        self.assertIn("12%", result)
        self.assertNotIn("[number redacted]", result)

    def test_text_without_numbers_unchanged(self) -> None:
        text = "Management expressed confidence in the business."
        result = _strip_invented_numbers(text, frozenset())
        self.assertEqual(result, text)

    def test_collect_allowed_numbers_from_chunks(self) -> None:
        chunks = [
            _make_chunk("c1", text="Revenue grew 12% and margins reached 25%."),
            _make_chunk("c2", text="EPS was $1.50 per share."),
        ]
        allowed = _collect_allowed_numbers(chunks, facts=None)
        self.assertIn("12%", allowed)
        self.assertIn("25%", allowed)
        self.assertIn("$1.50", allowed)

    def test_collect_allowed_numbers_from_facts(self) -> None:
        allowed = _collect_allowed_numbers(
            chunks=[],
            facts={"share_count_millions": "15500", "currency": "USD"},
        )
        self.assertIn("15500", allowed)


# ---------------------------------------------------------------------------
# h) Envelope unwrap + payload normalization (regression for bugs.md 2026-05-01)
# ---------------------------------------------------------------------------


class EnvelopeAndNormalizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_systemresponse_jsonobject_envelope_is_unwrapped(self) -> None:
        """qwen2.5:7b sometimes wraps the payload in systemResponse->jsonObject."""
        settings = _make_settings()
        chunks = [_make_chunk("c1"), _make_chunk("c2")]

        rag = MagicMock()
        rag.retrieve = AsyncMock(return_value=chunks)

        wrapped = {"systemResponse": {"jsonObject": _valid_llm_payload()}}
        ollama = MagicMock()
        ollama.generate_json = AsyncMock(return_value=wrapped)

        svc = QualitativeService(settings, rag, ollama)
        result = await svc.summarize("AAPL")

        self.assertEqual(result.tone, "positive")
        self.assertEqual(ollama.generate_json.call_count, 1)

    async def test_empty_enum_strings_are_coerced_to_safe_defaults(self) -> None:
        settings = _make_settings()
        chunks = [_make_chunk("c1"), _make_chunk("c2")]

        rag = MagicMock()
        rag.retrieve = AsyncMock(return_value=chunks)

        payload = _valid_llm_payload()
        payload["tone"] = ""
        payload["guidance_flavor"] = ""
        payload["evidence_quality"] = ""

        ollama = MagicMock()
        ollama.generate_json = AsyncMock(return_value=payload)

        svc = QualitativeService(settings, rag, ollama)
        result = await svc.summarize("AAPL")

        self.assertEqual(result.tone, "neutral")
        self.assertEqual(result.guidance_flavor, "none_mentioned")
        self.assertEqual(result.evidence_quality, "thin")
        self.assertEqual(ollama.generate_json.call_count, 1)

    async def test_list_returned_as_string_is_split(self) -> None:
        settings = _make_settings()
        chunks = [_make_chunk("c1"), _make_chunk("c2")]

        rag = MagicMock()
        rag.retrieve = AsyncMock(return_value=chunks)

        payload = _valid_llm_payload()
        payload["positives"] = "- Margin expansion noted.\n- Demand commentary upbeat."
        payload["risks"] = '["Macro pressure on spend.", "Supply chain remains a watchlist item."]'

        ollama = MagicMock()
        ollama.generate_json = AsyncMock(return_value=payload)

        svc = QualitativeService(settings, rag, ollama)
        result = await svc.summarize("AAPL")

        self.assertEqual(len(result.positives), 2)
        self.assertEqual(len(result.risks), 2)
        self.assertIn("Margin expansion", result.positives[0])
        self.assertIn("Macro pressure", result.risks[0])

    async def test_enum_synonyms_coerced(self) -> None:
        settings = _make_settings()
        chunks = [_make_chunk("c1"), _make_chunk("c2")]

        rag = MagicMock()
        rag.retrieve = AsyncMock(return_value=chunks)

        payload = _valid_llm_payload()
        payload["tone"] = "Bullish"
        payload["guidance_flavor"] = "maintained"
        payload["evidence_quality"] = "Medium"

        ollama = MagicMock()
        ollama.generate_json = AsyncMock(return_value=payload)

        svc = QualitativeService(settings, rag, ollama)
        result = await svc.summarize("AAPL")

        self.assertEqual(result.tone, "positive")
        self.assertEqual(result.guidance_flavor, "reaffirmed")
        self.assertEqual(result.evidence_quality, "moderate")


class UnwrapEnvelopeUnitTests(unittest.TestCase):
    def test_flat_payload_passthrough(self) -> None:
        payload = _valid_llm_payload()
        self.assertIs(_unwrap_envelope(payload), payload)

    def test_unwraps_multi_key_envelope(self) -> None:
        payload = _valid_llm_payload()
        wrapped = {"meta": {"version": 1}, "data": payload}
        self.assertEqual(_unwrap_envelope(wrapped), payload)

    def test_returns_original_when_no_match(self) -> None:
        payload = {"unrelated": "value"}
        self.assertEqual(_unwrap_envelope(payload), payload)


class NormalizePayloadUnitTests(unittest.TestCase):
    def test_drops_unknown_keys(self) -> None:
        raw = _valid_llm_payload()
        raw["unexpected"] = "garbage"
        out = _normalize_payload(raw)
        self.assertNotIn("unexpected", out)

    def test_replaces_service_managed_with_placeholders(self) -> None:
        raw = _valid_llm_payload()
        raw["prompt_version"] = "lies"
        raw["model_name"] = "lies"
        raw["chunk_ids"] = ["lies"]
        out = _normalize_payload(raw)
        self.assertEqual(out["prompt_version"], "pending")
        self.assertEqual(out["model_name"], "pending")
        self.assertEqual(out["chunk_ids"], [])


if __name__ == "__main__":
    unittest.main()
