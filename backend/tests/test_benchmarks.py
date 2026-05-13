"""Tests for analysis.benchmarks (GICS → SPDR sector ETF, Phase A)."""

from __future__ import annotations

import pytest

from backend.app.analysis import benchmarks as b


def test_broad_benchmark_from_yaml() -> None:
    assert b.BROAD_BENCHMARK_TICKER == "SPY"
    assert "S&P" in b.BROAD_BENCHMARK_NAME or "500" in b.BROAD_BENCHMARK_NAME
    assert b.get_broad_benchmark_ticker() == "SPY"


def test_list_sector_etf_names_covers_eleven_unique_tickers() -> None:
    rows = b.list_sector_etf_names()
    assert len(rows) == 11
    tickers = [r[1] for r in rows]
    assert len(set(tickers)) == 11
    assert set(tickers) == {
        "XLE",
        "XLB",
        "XLI",
        "XLY",
        "XLP",
        "XLV",
        "XLF",
        "XLK",
        "XLC",
        "XLU",
        "XLRE",
    }


@pytest.mark.parametrize(
    ("vendor_string", "expected"),
    [
        ("Energy", "XLE"),
        ("  energy  ", "XLE"),
        ("Information Technology", "XLK"),
        ("Technology", "XLK"),
        ("TECHNOLOGY", "XLK"),
        ("Consumer Discretionary", "XLY"),
        ("Consumer Cyclical", "XLY"),
        ("Consumer Staples", "XLP"),
        ("Consumer Defensive", "XLP"),
        ("Health Care", "XLV"),
        ("Healthcare", "XLV"),
        ("Financials", "XLF"),
        ("Financial Services", "XLF"),
        ("Communication Services", "XLC"),
        ("Telecommunication Services", "XLC"),
        ("Materials", "XLB"),
        ("Basic Materials", "XLB"),
        ("Real Estate", "XLRE"),
    ],
)
def test_sector_etf_ticker_aliases(vendor_string: str, expected: str) -> None:
    assert b.sector_etf_ticker(vendor_string) == expected


def test_sector_etf_ticker_none_on_empty_or_unknown() -> None:
    assert b.sector_etf_ticker(None) is None
    assert b.sector_etf_ticker("") is None
    assert b.sector_etf_ticker("   ") is None
    assert b.sector_etf_ticker("Not A Real Sector XYZ") is None
