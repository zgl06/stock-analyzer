"""Disk-based loader for canonical analysis fixtures.

Used by the Day 1 analysis stub so the downstream pipeline can be
exercised without depending on live ingestion or Supabase reads.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from backend.app.errors import NotFoundError, UpstreamServiceError
from backend.app.models import AnalysisInput


FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"


def fixture_path_for(ticker: str) -> Path:
    """Return the on-disk fixture path for a given ticker."""
    normalized = ticker.strip().lower()
    return FIXTURES_DIR / f"analysis-input-{normalized}.json"


@lru_cache(maxsize=32)
def _load_cached(normalized_ticker: str) -> AnalysisInput:
    path = FIXTURES_DIR / f"analysis-input-{normalized_ticker}.json"
    if not path.exists():
        raise NotFoundError(
            f"No analysis fixture found for ticker '{normalized_ticker.upper()}'."
        )

    try:
        raw = path.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise UpstreamServiceError(
            f"Failed to read fixture at {path}: {exc}"
        ) from exc

    return AnalysisInput.model_validate(payload)


def load_analysis_input_fixture(ticker: str) -> AnalysisInput:
    """Read and validate the AnalysisInput fixture for a ticker.

    Raises:
        NotFoundError: if no fixture exists for the ticker.
        UpstreamServiceError: if the fixture exists but cannot be parsed.
    """
    return _load_cached(ticker.strip().lower())


def available_fixture_tickers() -> list[str]:
    """List tickers that currently have a fixture on disk."""
    if not FIXTURES_DIR.exists():
        return []
    tickers: list[str] = []
    for entry in FIXTURES_DIR.glob("analysis-input-*.json"):
        stem = entry.stem.removeprefix("analysis-input-")
        if stem:
            tickers.append(stem.upper())
    return sorted(tickers)
