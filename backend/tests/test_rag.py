"""Tests for the L1 RAG foundation: chunker, HTML helper, and RagService.retrieve."""

from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.app.config import Settings
from backend.app.models.rag import RetrievedChunk
from backend.app.services._filing_text import html_to_text
from backend.app.services.rag import RagService, chunk_text, _estimate_tokens


_FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Chunker unit tests
# ---------------------------------------------------------------------------

class ChunkerTests(unittest.TestCase):
    def test_empty_text_returns_empty_list(self) -> None:
        self.assertEqual(chunk_text(""), [])

    def test_short_text_returns_single_chunk(self) -> None:
        text = "Hello world. This is a short sentence."
        chunks = chunk_text(text, chunk_size=3000, overlap=200)
        self.assertEqual(len(chunks), 1)
        self.assertIn("Hello world", chunks[0])

    def test_long_text_produces_multiple_chunks(self) -> None:
        # Build a text that is definitely larger than one chunk.
        sentence = "The quick brown fox jumps over the lazy dog. "
        text = sentence * 100  # ~4500 chars
        chunks = chunk_text(text, chunk_size=3000, overlap=200)
        self.assertGreater(len(chunks), 1)

    def test_overlap_present_between_chunks(self) -> None:
        sentence = "Revenue risk is the primary concern for management. "
        text = sentence * 100
        chunks = chunk_text(text, chunk_size=3000, overlap=200)
        if len(chunks) >= 2:
            # The tail of chunk[0] should share some content with the head of chunk[1].
            tail = chunks[0][-200:]
            head = chunks[1][:200]
            # At least some words should appear in both.
            tail_words = set(tail.split())
            head_words = set(head.split())
            self.assertTrue(tail_words & head_words, "Expected overlap between consecutive chunks.")

    def test_deterministic_chunk_count(self) -> None:
        text = "A" * 9_000
        chunks1 = chunk_text(text, chunk_size=3000, overlap=200)
        chunks2 = chunk_text(text, chunk_size=3000, overlap=200)
        self.assertEqual(len(chunks1), len(chunks2))
        self.assertEqual(chunks1, chunks2)

    def test_chunk_size_respected(self) -> None:
        text = "x" * 9_000
        chunks = chunk_text(text, chunk_size=3000, overlap=200)
        for chunk in chunks:
            # Allow a small margin for sentence-boundary adjustment.
            self.assertLessEqual(len(chunk), 3000 + 50)

    def test_estimate_tokens(self) -> None:
        self.assertEqual(_estimate_tokens(""), 1)
        self.assertEqual(_estimate_tokens("a" * 400), 100)


# ---------------------------------------------------------------------------
# HTML-to-text unit tests
# ---------------------------------------------------------------------------

class HtmlToTextTests(unittest.TestCase):
    def test_strips_script_and_style(self) -> None:
        html = "<html><head><script>alert(1)</script><style>.x{}</style></head><body><p>Hello</p></body></html>"
        text = html_to_text(html)
        self.assertNotIn("alert", text)
        self.assertNotIn(".x{}", text)
        self.assertIn("Hello", text)

    def test_strips_nav_and_footer(self) -> None:
        html = "<html><body><nav>Nav item</nav><p>Content</p><footer>Footer</footer></body></html>"
        text = html_to_text(html)
        self.assertNotIn("Nav item", text)
        self.assertNotIn("Footer", text)
        self.assertIn("Content", text)

    def test_fixture_file_roundtrip(self) -> None:
        fixture = _FIXTURES / "sample_10k.html"
        html = fixture.read_text(encoding="utf-8")
        text = html_to_text(html)
        # Script and style should be gone.
        self.assertNotIn("var x = 1", text)
        self.assertNotIn("font-family", text)
        # Key content must survive.
        self.assertIn("Acme Corp", text)
        self.assertIn("risk factors", text.lower())

    def test_collapses_whitespace(self) -> None:
        html = "<p>Hello     world</p><p>   </p><p>   </p><p>Next para</p>"
        text = html_to_text(html)
        self.assertNotIn("  ", text)  # no double spaces
        self.assertIn("Hello world", text)


# ---------------------------------------------------------------------------
# RagService.retrieve integration-shaped test (all Supabase + model mocked)
# ---------------------------------------------------------------------------

class RagServiceRetrieveTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.settings = Settings(
            supabase_url="https://example.supabase.co",
            supabase_service_role_key="fake-key",
            sec_user_agent="test-agent",
        )

    def _make_service_with_mocks(
        self,
        company_id: str = "uuid-company-1",
        rpc_rows: list[dict] | None = None,
        query_vector: list[float] | None = None,
    ) -> tuple[RagService, MagicMock]:
        """Build a RagService whose Supabase client and embedding model are mocked."""
        if rpc_rows is None:
            rpc_rows = [
                {
                    "id": "uuid-chunk-1",
                    "accession_number": "0000123456-24-000001",
                    "filing_type": "10-K",
                    "filing_date": "2024-01-15",
                    "text": "Revenue risk is a major concern for our margins.",
                    "token_count": 12,
                    "score": 0.85,
                },
                {
                    "id": "uuid-chunk-2",
                    "accession_number": "0000123456-24-000001",
                    "filing_type": "10-K",
                    "filing_date": "2024-01-15",
                    "text": "Supply chain disruptions could materially harm results.",
                    "token_count": 10,
                    "score": 0.60,
                },
                {
                    "id": "uuid-chunk-3",
                    "accession_number": "0000123456-24-000001",
                    "filing_type": "10-K",
                    "filing_date": "2024-01-15",
                    "text": "Low score chunk should be filtered out.",
                    "token_count": 8,
                    "score": 0.10,  # below min_score
                },
            ]
        if query_vector is None:
            query_vector = [0.1] * 384

        service = RagService(self.settings)

        # Mock supabase client.
        mock_client = MagicMock()
        service._client = mock_client

        # companies lookup
        companies_resp = MagicMock()
        companies_resp.data = [{"id": company_id}]
        mock_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = companies_resp

        # rpc call
        rpc_resp = MagicMock()
        rpc_resp.data = rpc_rows
        mock_client.rpc.return_value.execute.return_value = rpc_resp

        return service, mock_client, query_vector

    async def test_retrieve_returns_ranked_chunks(self) -> None:
        service, mock_client, query_vector = self._make_service_with_mocks()

        with patch("backend.app.services.rag._embed", return_value=[query_vector]):
            results = await service.retrieve("ACME", "revenue risk", k=6, min_score=0.2)

        self.assertEqual(len(results), 2, "Should drop the chunk with score < 0.2")
        self.assertIsInstance(results[0], RetrievedChunk)
        self.assertEqual(results[0].score, 0.85)
        self.assertEqual(results[1].score, 0.60)

    async def test_retrieve_respects_k(self) -> None:
        # Build 5 rows all above threshold.
        rows = [
            {
                "id": f"uuid-chunk-{i}",
                "accession_number": "0000111111-24-000001",
                "filing_type": "10-Q",
                "filing_date": "2024-03-01",
                "text": f"Chunk {i} content.",
                "token_count": 5,
                "score": 0.9 - i * 0.05,
            }
            for i in range(5)
        ]
        service, mock_client, query_vector = self._make_service_with_mocks(rpc_rows=rows)

        with patch("backend.app.services.rag._embed", return_value=[query_vector]):
            # k=3 is passed to the RPC; the mock returns all 5 but the RPC is called with k=3.
            results = await service.retrieve("ACME", "query", k=3, min_score=0.1)

        # Verify the RPC was called with match_count=3.
        mock_client.rpc.assert_called_once_with(
            "match_filing_chunks",
            {
                "query_embedding": query_vector,
                "match_count": 3,
                "p_company_id": "uuid-company-1",
            },
        )
        # All 5 rows pass the score filter in our mock; results should be all 5
        # (the mock ignores k, that's fine — the real Postgres function limits).
        self.assertGreater(len(results), 0)

    async def test_retrieve_respects_max_tokens(self) -> None:
        # Each chunk is 200 tokens; max_tokens=350 => only 1 chunk fits.
        rows = [
            {
                "id": "uuid-chunk-1",
                "accession_number": "0000222222-24-000001",
                "filing_type": "8-K",
                "filing_date": "2024-06-01",
                "text": "First big chunk.",
                "token_count": 200,
                "score": 0.80,
            },
            {
                "id": "uuid-chunk-2",
                "accession_number": "0000222222-24-000001",
                "filing_type": "8-K",
                "filing_date": "2024-06-01",
                "text": "Second big chunk.",
                "token_count": 200,
                "score": 0.70,
            },
        ]
        service, mock_client, query_vector = self._make_service_with_mocks(rpc_rows=rows)

        with patch("backend.app.services.rag._embed", return_value=[query_vector]):
            results = await service.retrieve("ACME", "query", k=6, max_tokens=350, min_score=0.1)

        self.assertEqual(len(results), 1, "Second chunk should be cut off by token budget.")

    async def test_retrieve_chunk_fields_populated(self) -> None:
        service, mock_client, query_vector = self._make_service_with_mocks()

        with patch("backend.app.services.rag._embed", return_value=[query_vector]):
            results = await service.retrieve("ACME", "revenue risk")

        chunk = results[0]
        self.assertEqual(chunk.chunk_id, "uuid-chunk-1")
        self.assertEqual(chunk.filing_type, "10-K")
        self.assertEqual(chunk.filing_date, date(2024, 1, 15))
        self.assertIn("Revenue risk", chunk.text)


if __name__ == "__main__":
    unittest.main()
