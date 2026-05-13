"""Tests for analysis.returns (Phase B: total return from adjusted closes, mocked yfinance)."""

from __future__ import annotations

import os
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from backend.app.analysis.returns import total_return_simple


def _make_hist(rows: list[tuple[str, float]]) -> pd.DataFrame:
    """rows: (YYYY-MM-DD, close)."""
    idx = pd.to_datetime([r[0] for r in rows])
    return pd.DataFrame({"Close": [r[1] for r in rows]}, index=idx)


def test_total_return_two_day_window() -> None:
    """100 -> 110 over two closes is 10% simple return."""
    mock_t = MagicMock()
    mock_t.history.return_value = _make_hist(
        [
            ("2024-01-02", 100.0),
            ("2024-01-03", 110.0),
        ]
    )
    start = date(2024, 1, 2)
    end = date(2024, 1, 3)
    r = total_return_simple("SPY", start, end, _yf_ticker=mock_t)
    assert r is not None
    assert abs(r - 0.1) < 1e-9
    mock_t.history.assert_called_once()


def test_end_before_start_none() -> None:
    m = MagicMock()
    assert total_return_simple("SPY", date(2024, 1, 3), date(2024, 1, 2), _yf_ticker=m) is None
    m.history.assert_not_called()


def test_empty_history_none() -> None:
    m = MagicMock()
    m.history.return_value = pd.DataFrame()
    assert (
        total_return_simple(
            "SPY",
            date(2020, 1, 1),
            date(2020, 12, 31),
            _yf_ticker=m,
        )
        is None
    )


def test_xlre_none_when_start_before_inception() -> None:
    m = MagicMock()
    m.history.return_value = _make_hist(
        [
            ("2015-10-8", 20.0),
            ("2015-10-9", 21.0),
        ]
    )
    with patch("backend.app.analysis.returns._first_trade_date_utc", return_value=date(2015, 10, 8)):
        r = total_return_simple("XLRE", date(2010, 1, 1), date(2015, 10, 9), _yf_ticker=m)
    assert r is None
    m.history.assert_not_called()


def test_xlre_ok_when_start_after_inception() -> None:
    m = MagicMock()
    m.history.return_value = _make_hist(
        [
            ("2015-10-8", 20.0),
            ("2015-10-9", 22.0),
        ]
    )
    with patch("backend.app.analysis.returns._first_trade_date_utc", return_value=date(2015, 10, 8)):
        r = total_return_simple("XLRE", date(2015, 10, 8), date(2015, 10, 9), _yf_ticker=m)
    assert r is not None
    assert abs(r - 0.1) < 1e-9


def test_weekend_end_uses_friday_close() -> None:
    """``end`` on Sunday still uses last available close in range (Friday)."""
    m = MagicMock()
    m.history.return_value = _make_hist(
        [
            ("2024-01-04", 100.0),
            ("2024-01-05", 102.0),
        ]
    )
    r = total_return_simple("SPY", date(2024, 1, 4), date(2024, 1, 7), _yf_ticker=m)
    assert r is not None
    assert abs(r - 0.02) < 1e-9


@pytest.mark.skipif(
    not os.environ.get("RUN_YFINANCE_SMOKE"),
    reason="set RUN_YFINANCE_SMOKE=1 for an optional yfinance network sanity check",
)
def test_spy_one_year_sanity_against_broad_magnitude() -> None:
    """Optional real call: 1Y SPY return should be a modest fraction (not order unity)."""
    end = date.today() - timedelta(days=3)
    start = end - timedelta(days=365)
    r = total_return_simple("SPY", start, end)
    assert r is not None
    assert -0.5 < r < 0.5
