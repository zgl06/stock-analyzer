"""Tests for analysis.excess_returns (Phase C: 5y excess vs SPY and sector)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import numpy as np
import pandas as pd

from backend.app.analysis.excess_returns import (
    add_calendar_years,
    five_year_excess_table,
    resolve_sector_name,
)


def test_add_calendar_years_feb_29() -> None:
    assert add_calendar_years(date(2020, 2, 29), 5) == date(2025, 2, 28)


def test_five_year_excess_happy_path_mocked() -> None:
    """Fixed returns: stock 50%, SPY 10%, sector ETF 20% => excess 40% and 30%."""
    a0 = date(2015, 6, 1)
    a1 = date(2015, 6, 15)

    def tr(sym: str, start: date, end: date) -> float | None:  # noqa: ARG001
        m = {
            "AAPL": 0.50,
            "SPY": 0.10,
            "XLK": 0.20,
        }
        return m.get(sym)

    df = five_year_excess_table(
        "AAPL",
        [a0, a1],
        sector="Information Technology",
        _total_return=tr,
    )
    assert len(df) == 2
    assert (df["mapped_sector_etf"] == "XLK").all()
    assert not df["parent_spy_filled"].any()
    assert np.allclose(df["excess_spy"], 0.40, rtol=0, atol=1e-9)
    assert np.allclose(df["excess_sector"], 0.30, rtol=0, atol=1e-9)


def test_parent_spy_fills_when_sector_etf_fails() -> None:
    def tr(sym: str, start: date, end: date) -> float | None:  # noqa: ARG001
        if sym == "XLE":
            return None
        if sym == "SPY":
            return 0.10
        if sym == "XOM":
            return 0.30
        return None

    df = five_year_excess_table(
        "XOM",
        [date(2015, 1, 1)],
        sector="Energy",
        _total_return=tr,
    )
    assert len(df) == 1
    assert bool(df.loc[0, "parent_spy_filled"])
    assert df.loc[0, "sector_bench_ticker"] == "SPY"
    assert df.loc[0, "r_sector_5y"] == 0.10
    # excess_spy and excess_sector both 0.20
    assert np.isclose(df.loc[0, "excess_spy"], 0.20)
    assert np.isclose(df.loc[0, "excess_sector"], 0.20)


def test_no_parent_fill_when_flag_off() -> None:
    def tr(sym: str, start: date, end: date) -> float | None:  # noqa: ARG001
        if sym == "XLE":
            return None
        if sym == "SPY":
            return 0.1
        if sym == "XOM":
            return 0.3
        return None

    df = five_year_excess_table(
        "XOM",
        [date(2015, 1, 1)],
        sector="Energy",
        use_spy_if_sector_etf_fails=False,
        _total_return=tr,
    )
    assert pd.isna(df.loc[0, "r_sector_5y"])
    assert pd.isna(df.loc[0, "excess_sector"])


def test_unmapped_sector_no_excess_sector() -> None:
    def tr(sym: str, start: date, end: date) -> float | None:  # noqa: ARG001
        if sym in ("AAPL", "SPY"):
            return 0.1
        return None

    df = five_year_excess_table(
        "AAPL",
        [date(2015, 1, 1)],
        sector="Not a GICS sector",
        _total_return=tr,
    )
    assert pd.isna(df.loc[0, "mapped_sector_etf"])
    assert pd.isna(df.loc[0, "r_sector_5y"])
    assert pd.isna(df.loc[0, "excess_sector"])


def test_empty_as_of() -> None:
    df = five_year_excess_table("AAPL", [], sector="Technology", _total_return=lambda *a, **k: 0.0)
    assert df.empty


def test_resolve_sector_name_from_yfinance() -> None:
    m = MagicMock()
    m.info = {"sector": "Technology"}
    r = resolve_sector_name("AAPL", None, _yf=m)
    assert r.gics_or_vendor == "Technology"
    assert r.etf == "XLK"
    assert r.source == "yfinance"
