"""Tests for analysis.label_returns (Phase D: M&A label policy)."""

from __future__ import annotations

from datetime import date

import pytest

from backend.app.analysis.label_returns import (
    MERGER_OVERRIDES,
    clear_merger_overrides,
    register_merger_override,
    total_return_stock_for_label,
)


@pytest.fixture(autouse=True)
def _reset_overrides() -> object:
    clear_merger_overrides()
    yield
    clear_merger_overrides()


def test_direct_return_skips_merger() -> None:
    def tr(sym: str, start: date, end: date) -> float | None:  # noqa: ARG001
        return 0.05 if sym == "AAA" else None

    r = total_return_stock_for_label("AAA", date(2010, 1, 1), date(2015, 1, 1), _inner=tr)
    assert r.value == 0.05
    assert r.symbol_used == "AAA"
    assert r.skip_reason is None
    assert r.merger_note is None


def test_merger_spans_window_skips() -> None:
    register_merger_override("OLDCO", "NEWCO", date(2012, 6, 15))

    def tr(sym: str, start: date, end: date) -> float | None:  # noqa: ARG001
        if sym == "OLDCO":
            return None
        if sym == "NEWCO":
            return 0.2
        return None

    r = total_return_stock_for_label("OLDCO", date(2010, 1, 1), date(2015, 1, 1), _inner=tr)
    assert r.value is None
    assert r.skip_reason == "merger_spans_window"
    assert r.symbol_used == "OLDCO"


def test_post_merger_uses_acquirer() -> None:
    register_merger_override("OLDCO", "NEWCO", date(2000, 1, 1))

    def tr(sym: str, start: date, end: date) -> float | None:  # noqa: ARG001
        if sym == "OLDCO":
            return None
        if sym == "NEWCO":
            return 0.33
        return None

    r = total_return_stock_for_label("OLDCO", date(2010, 1, 1), date(2015, 1, 1), _inner=tr)
    assert r.value == 0.33
    assert r.symbol_used == "NEWCO"
    assert r.skip_reason is None
    assert r.merger_note == "acquirer_post_merger"


def test_no_override_yields_unavailable() -> None:
    def tr(sym: str, start: date, end: date) -> float | None:  # noqa: ARG001
        return None

    r = total_return_stock_for_label("ZZZ", date(2010, 1, 1), date(2015, 1, 1), _inner=tr)
    assert r.value is None
    assert r.skip_reason == "yfinance_unavailable"
    assert "ZZZ" not in MERGER_OVERRIDES
