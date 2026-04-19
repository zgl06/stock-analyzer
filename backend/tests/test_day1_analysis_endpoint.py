"""Day 1 verification for GET /analysis/{ticker}."""

from __future__ import annotations

import pytest

try:
    from fastapi.testclient import TestClient

    from backend.app.main import app
except Exception as exc:  # pragma: no cover - environment-dependent
    pytest.skip(
        f"Skipping endpoint tests: backend app cannot be imported ({exc!r}).",
        allow_module_level=True,
    )


client = TestClient(app)


def test_get_analysis_returns_assembled_stub_for_known_ticker() -> None:
    response = client.get("/analysis/aapl")

    assert response.status_code == 200
    payload = response.json()

    assert payload["ticker"] == "AAPL"
    assert payload["source"] == "fixture"
    assert payload["company"]["ticker"] == "AAPL"

    assert "marketData" in payload["analysis_input"]
    assert payload["score"]["pillars"], "pillars should be present in the score breakdown"

    scenarios = {s["scenario"] for s in payload["forecast"]}
    assert scenarios == {"bear", "base", "bull"}

    assert payload["verdict"]["rating"] in {"Strong Buy", "Buy", "Hold", "Avoid"}
    assert isinstance(payload["peers"], list) and len(payload["peers"]) > 0


def test_get_analysis_returns_404_for_unknown_ticker() -> None:
    response = client.get("/analysis/zzzz")

    assert response.status_code == 404
    assert "fixture" in response.json()["detail"].lower()
