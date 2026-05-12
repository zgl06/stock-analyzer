"""L3 tests: qualitative summary wiring in GET /analysis/{ticker}."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

try:
    from fastapi.testclient import TestClient

    from backend.app.errors import LLMError
    from backend.app.main import app
    from backend.app.api import routes as api_routes
    from backend.app.models.document_summary import DocumentSummary
    from backend.app.services._qual_prompts import PROMPT_VERSION
    from backend.app.services.fixture_loader import load_analysis_input_fixture
    from backend.app.services.qualitative import QualitativeService, QUALITATIVE_TTL_HOURS
    from backend.app.models.rag import RetrievedChunk
except Exception as exc:  # pragma: no cover
    pytest.skip(
        f"Skipping qualitative route tests: backend app cannot be imported ({exc!r}).",
        allow_module_level=True,
    )


client = TestClient(app)

_MODEL = "qwen2.5:7b"
_PROMPT = PROMPT_VERSION


def _make_document_summary() -> DocumentSummary:
    return DocumentSummary(
        tone="positive",
        thesis="The company demonstrated solid execution.",
        positives=["Operating leverage improved.", "Strong demand outlook."],
        risks=["Macro uncertainty.", "Supply chain watch."],
        guidance_flavor="reaffirmed",
        evidence_quality="moderate",
        prompt_version=_PROMPT,
        model_name=_MODEL,
        chunk_ids=["c1", "c2"],
    )


def _base_settings(*, enable_qualitative: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        has_supabase=True,
        schema_version="v1",
        enable_qualitative_summary=enable_qualitative,
        ollama_model=_MODEL,
        ollama_base_url="http://localhost:11434",
        ollama_timeout_s=120.0,
        supabase_url="http://fake",
        supabase_service_role_key="fake",
    )


def _patch_base(monkeypatch: pytest.MonkeyPatch, *, enable_qualitative: bool = False) -> None:
    """Patch storage + market snapshot so the core pipeline works without Supabase."""
    fixture_row = load_analysis_input_fixture("AAPL").model_dump(mode="json")

    class _FakeStorage:
        def __init__(self, settings=None):
            pass

        async def get_latest_analysis_input(self, ticker: str):
            return fixture_row

    async def _noop_attach(ai, *, settings=None):
        return ai

    monkeypatch.setattr(api_routes, "StorageService", _FakeStorage)
    monkeypatch.setattr(api_routes, "attach_fresh_market_snapshot", _noop_attach)
    monkeypatch.setattr(
        api_routes,
        "get_settings",
        lambda: _base_settings(enable_qualitative=enable_qualitative),
    )


# ---------------------------------------------------------------------------
# a) Flag off — qualitative not called, response has document_summary=None
# ---------------------------------------------------------------------------

def test_flag_off_qualitative_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_base(monkeypatch, enable_qualitative=False)

    summarize_called = []

    async def _fake_summarize(ticker: str, **kwargs):
        summarize_called.append(ticker)
        return _make_document_summary()

    monkeypatch.setattr(api_routes, "QualitativeService", MagicMock())

    response = client.get("/analysis/aapl")
    assert response.status_code == 200
    payload = response.json()
    assert payload["document_summary"] is None
    assert not summarize_called


# ---------------------------------------------------------------------------
# b) Flag on, summarize returns valid summary
# ---------------------------------------------------------------------------

def test_flag_on_returns_document_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_base(monkeypatch, enable_qualitative=True)

    summary = _make_document_summary()

    async def _fake_resolve_qual(*, ticker: str, settings) -> DocumentSummary:
        return summary

    monkeypatch.setattr(api_routes, "_resolve_qualitative_summary", _fake_resolve_qual)

    response = client.get("/analysis/aapl")
    assert response.status_code == 200
    payload = response.json()
    ds = payload["document_summary"]
    assert ds is not None
    assert ds["tone"] == "positive"
    assert ds["prompt_version"] == _PROMPT
    assert ds["model_name"] == _MODEL


# ---------------------------------------------------------------------------
# c) Flag on, QualitativeService.summarize raises LLMError — 200, None
# ---------------------------------------------------------------------------

def test_flag_on_llm_error_graceful_degradation(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_base(monkeypatch, enable_qualitative=True)

    class _FailSvc:
        def __init__(self, *a, **kw):
            pass

        async def summarize(self, ticker: str, **kwargs):
            raise LLMError("Ollama timed out")

    monkeypatch.setattr(api_routes, "QualitativeService", _FailSvc)

    response = client.get("/analysis/aapl")
    assert response.status_code == 200
    assert response.json()["document_summary"] is None


# ---------------------------------------------------------------------------
# d) Flag on, QualitativeService.summarize raises generic Exception — 200, None
# ---------------------------------------------------------------------------

def test_flag_on_generic_exception_graceful_degradation(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_base(monkeypatch, enable_qualitative=True)

    class _FailSvc:
        def __init__(self, *a, **kw):
            pass

        async def summarize(self, ticker: str, **kwargs):
            raise RuntimeError("unexpected failure")

    monkeypatch.setattr(api_routes, "QualitativeService", _FailSvc)

    response = client.get("/analysis/aapl")
    assert response.status_code == 200
    assert response.json()["document_summary"] is None


# ---------------------------------------------------------------------------
# e) _resolve_qualitative_summary: LLMError and generic Exception both return None
# ---------------------------------------------------------------------------

class ResolveQualitativeSummaryTests(unittest.IsolatedAsyncioTestCase):
    async def _call(self, exc: Exception) -> None:
        import importlib
        routes_mod = importlib.import_module("backend.app.api.routes")

        settings = _base_settings(enable_qualitative=True)

        class _FakeSvc:
            def __init__(self, *a, **kw):
                pass

            async def summarize(self, ticker, **kwargs):
                raise exc

        orig = routes_mod.QualitativeService
        routes_mod.QualitativeService = _FakeSvc  # type: ignore[attr-defined]
        try:
            result = await routes_mod._resolve_qualitative_summary(
                ticker="AAPL", settings=settings
            )
        finally:
            routes_mod.QualitativeService = orig  # type: ignore[attr-defined]
        return result

    async def test_llm_error_returns_none(self) -> None:
        result = await self._call(LLMError("bad"))
        self.assertIsNone(result)

    async def test_runtime_error_returns_none(self) -> None:
        result = await self._call(RuntimeError("oops"))
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# f) QualitativeService.get_cached — Supabase mock tests
# ---------------------------------------------------------------------------

def _make_chunk(chunk_id: str = "c1") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        accession_number="0000000000-24-000001",
        filing_type="10-K",
        filing_date=date(2024, 1, 15),
        text="Operating margin expanded.",
        score=0.9,
        token_count=10,
    )


def _make_settings_ns() -> SimpleNamespace:
    return SimpleNamespace(
        has_supabase=True,
        supabase_url="http://fake",
        supabase_service_role_key="fake",
        ollama_model=_MODEL,
        ollama_base_url="http://localhost:11434",
        ollama_timeout_s=120.0,
    )


class GetCachedTests(unittest.TestCase):
    def _make_svc(self, client_mock: MagicMock) -> QualitativeService:
        from backend.app.config import Settings
        settings = Settings(
            supabase_url="http://fake",
            supabase_service_role_key="fake",
            ollama_base_url="http://localhost:11434",
            ollama_model=_MODEL,
        )
        svc = QualitativeService(settings, MagicMock(), MagicMock())
        svc._client = client_mock
        return svc

    def _summary_payload(self) -> dict:
        return _make_document_summary().model_dump(mode="json")

    def test_returns_summary_on_cache_hit(self) -> None:
        fresh_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        fake_client = MagicMock()
        # companies lookup
        fake_client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [{"id": "cid-1"}]

        def _table(name: str):
            t = MagicMock()
            if name == "companies":
                t.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [{"id": "cid-1"}]
            else:
                t.select.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
                    {"payload": self._summary_payload(), "created_at": fresh_ts}
                ]
            return t

        fake_client.table = _table
        svc = self._make_svc(fake_client)
        result = svc.get_cached("AAPL")
        assert result is not None
        assert isinstance(result, DocumentSummary)
        assert result.tone == "positive"

    def test_returns_none_when_expired(self) -> None:
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=QUALITATIVE_TTL_HOURS + 1)).isoformat()

        def _table(name: str):
            t = MagicMock()
            if name == "companies":
                t.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [{"id": "cid-1"}]
            else:
                t.select.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
                    {"payload": self._summary_payload(), "created_at": old_ts}
                ]
            return t

        fake_client = MagicMock()
        fake_client.table = _table
        svc = self._make_svc(fake_client)
        result = svc.get_cached("AAPL")
        assert result is None

    def test_returns_none_when_no_row(self) -> None:
        def _table(name: str):
            t = MagicMock()
            if name == "companies":
                t.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [{"id": "cid-1"}]
            else:
                t.select.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
            return t

        fake_client = MagicMock()
        fake_client.table = _table
        svc = self._make_svc(fake_client)
        result = svc.get_cached("AAPL")
        assert result is None

    def test_returns_none_when_company_not_found(self) -> None:
        def _table(name: str):
            t = MagicMock()
            t.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
            return t

        fake_client = MagicMock()
        fake_client.table = _table
        svc = self._make_svc(fake_client)
        result = svc.get_cached("ZZZZZ")
        assert result is None
