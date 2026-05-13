"""Day 1 verification for GET /analysis/{ticker}."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

try:
    from fastapi.testclient import TestClient

    from backend.app.errors import NotFoundError
    from backend.app.main import app
    from backend.app.api import routes as api_routes
    from backend.app.services.fixture_loader import load_analysis_input_fixture
except Exception as exc:  # pragma: no cover - environment-dependent
    pytest.skip(
        f"Skipping endpoint tests: backend app cannot be imported ({exc!r}).",
        allow_module_level=True,
    )


client = TestClient(app)


def _patch_supabase_fixture_row_no_live_market(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve stored AAPL snapshot from Supabase without calling yfinance."""

    fixture_row = load_analysis_input_fixture("AAPL").model_dump(mode="json")

    class _FakeStorageService:
        def __init__(self, settings=None):  # noqa: ARG002
            pass

        async def get_latest_analysis_input(self, ticker: str):  # noqa: ARG002
            return fixture_row

    async def _noop_attach(ai, *, settings=None):  # noqa: ARG002
        return ai

    monkeypatch.setattr(api_routes, "StorageService", _FakeStorageService)
    monkeypatch.setattr(api_routes, "attach_fresh_market_snapshot", _noop_attach)
    monkeypatch.setattr(
        api_routes,
        "get_settings",
        lambda: SimpleNamespace(
            has_supabase=True,
            schema_version="v1",
            enable_qualitative_summary=False,
        ),
    )


def _patch_supabase_empty_and_ingestion_fails(
    monkeypatch: pytest.MonkeyPatch, *, detail: str
) -> None:
    class _EmptyStorageService:
        def __init__(self, settings=None):  # noqa: ARG002
            pass

        async def get_latest_analysis_input(self, ticker: str):  # noqa: ARG002
            raise NotFoundError(detail)

    async def _ingest_fail(_ticker: str):  # noqa: ARG002
        raise NotFoundError(detail)

    monkeypatch.setattr(api_routes, "StorageService", _EmptyStorageService)
    monkeypatch.setattr(api_routes, "run_ingestion", _ingest_fail)
    monkeypatch.setattr(
        api_routes,
        "get_settings",
        lambda: SimpleNamespace(
            has_supabase=True,
            schema_version="v1",
            enable_qualitative_summary=False,
        ),
    )


def test_get_analysis_returns_assembled_live_from_storage_stub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_supabase_fixture_row_no_live_market(monkeypatch)

    response = client.get("/analysis/aapl")

    assert response.status_code == 200
    payload = response.json()

    assert payload["ticker"] == "AAPL"
    assert payload["source"] == "live"
    assert payload["company"]["ticker"] == "AAPL"

    assert "marketData" in payload["analysis_input"]
    assert payload["score"]["pillars"], "pillars should be present in the score breakdown"

    scenarios = {s["scenario"] for s in payload["forecast"]}
    assert scenarios == {"bear", "base", "bull"}

    assert payload["verdict"]["rating"] in {"Strong Buy", "Buy", "Hold", "Avoid"}
    assert isinstance(payload["peers"], list)


def test_get_analysis_returns_404_for_unknown_ticker(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_supabase_empty_and_ingestion_fails(
        monkeypatch, detail="Ticker ZZZZ is unknown."
    )

    response = client.get("/analysis/zzzz")

    assert response.status_code == 404
    detail = response.json()["detail"].lower()
    assert "zzzz" in detail


def test_get_relative_model_endpoint_shape_for_known_ticker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_supabase_fixture_row_no_live_market(monkeypatch)

    response = client.get("/analysis/aapl/relative-model")
    assert response.status_code == 200
    payload = response.json()
    assert payload["horizon_years"] == 5
    assert "as_of" in payload
    assert "vs_spy" in payload
    assert "vs_sector" in payload
    assert payload["vs_spy"]["benchmark_ticker"] == "SPY"
    assert payload["vs_spy"]["methodology"] in {"lightgbm", "unavailable", "score_proxy"}
    assert payload["vs_sector"]["methodology"] in {"lightgbm", "unavailable", "score_proxy"}
    assert isinstance(payload["disclaimer"], str) and payload["disclaimer"]


def test_get_relative_model_endpoint_sector_model_available_for_known_sector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_supabase_fixture_row_no_live_market(monkeypatch)

    response = client.get("/analysis/aapl/relative-model")
    assert response.status_code == 200
    payload = response.json()
    if payload["sector_etf"]:
        assert payload["vs_sector"]["benchmark_ticker"] == payload["sector_etf"]
        assert payload["vs_sector"]["methodology"] in {"lightgbm", "unavailable"}


def test_get_analysis_falls_back_when_relative_model_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_supabase_fixture_row_no_live_market(monkeypatch)

    class _BrokenService:
        def get_relative_view(self, *, ticker: str, sector: str | None):  # noqa: ARG002
            raise RuntimeError("simulated missing model artifacts")

    monkeypatch.setattr(api_routes, "_relative_model_service", _BrokenService())
    response = client.get("/analysis/aapl")
    assert response.status_code == 200
    payload = response.json()
    rel = payload["relative_performance"]
    assert rel is not None
    assert rel["vs_spy"]["methodology"] == "unavailable"
    detail = (rel["vs_spy"]["detail"] or "").lower()
    assert "unavailable" in detail or "missing" in detail or "relative model" in detail


def test_get_analysis_sector_fallback_when_sector_model_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_supabase_fixture_row_no_live_market(monkeypatch)

    from backend.app.models.analysis_output import (
        RelativePerformanceView,
        RelativeTercileEstimate,
    )

    class _OnlySpyService:
        def get_relative_view(self, *, ticker: str, sector: str | None):
            return RelativePerformanceView(
                horizon_years=5,
                as_of="2026-01-01",
                gics_sector=sector,
                sector_etf="XLK" if sector else None,
                used_parent_etf=False,
                vs_spy=RelativeTercileEstimate(
                    benchmark_ticker="SPY",
                    tercile=3,
                    score=0.9,
                    methodology="lightgbm",
                    detail="ok",
                ),
                vs_sector=RelativeTercileEstimate(
                    benchmark_ticker="XLK",
                    tercile=None,
                    score=None,
                    methodology="unavailable",
                    detail="sector artifacts missing",
                ),
            )

    monkeypatch.setattr(api_routes, "_relative_model_service", _OnlySpyService())
    response = client.get("/analysis/aapl")
    assert response.status_code == 200
    payload = response.json()
    rel = payload["relative_performance"]
    assert rel is not None
    assert rel["vs_spy"]["methodology"] == "lightgbm"
    assert rel["vs_sector"]["methodology"] == "unavailable"
