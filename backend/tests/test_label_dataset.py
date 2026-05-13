"""Tests for analysis.label_dataset (Phase E batch label generation)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from backend.app.analysis.label_dataset import (
    build_label_dataset,
    generate_as_of_dates,
    load_sector_file,
    load_tickers_file,
    read_existing_label_output,
    write_label_output,
)


def _fake_build(
    ticker: str,
    as_of_dates: list[date],
    *,
    sector: str | None = None,
    use_spy_if_sector_etf_fails: bool = True,  # noqa: ARG001
    merger_aware: bool = True,  # noqa: ARG001
) -> pd.DataFrame:
    rows = []
    for a in as_of_dates:
        rows.append(
            {
                "ticker": ticker,
                "as_of": a,
                "end_date": date(a.year + 5, a.month, min(a.day, 28)),
                "gics_or_vendor": sector,
                "r_stock_5y": 0.20,
                "r_spy_5y": 0.10,
                "r_sector_5y": 0.12,
                "excess_spy": 0.10,
                "excess_sector": 0.08,
                "sector_bench_ticker": "XLK",
                "parent_spy_filled": False,
                "mapped_sector_etf": "XLK",
                "stock_label_symbol": ticker,
                "stock_label_skip_reason": None,
                "stock_label_merger_note": None,
            }
        )
    return pd.DataFrame(rows)


def test_generate_as_of_dates_monthly_and_quarterly() -> None:
    monthly = generate_as_of_dates(date(2020, 1, 1), date(2020, 3, 31), "monthly")
    quarterly = generate_as_of_dates(date(2020, 1, 1), date(2020, 12, 31), "quarterly")
    assert monthly == [date(2020, 1, 1), date(2020, 2, 1), date(2020, 3, 1)]
    assert quarterly == [
        date(2020, 1, 1),
        date(2020, 4, 1),
        date(2020, 7, 1),
        date(2020, 10, 1),
    ]


def test_build_label_dataset_resume_skips_existing() -> None:
    existing = pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "as_of": date(2020, 1, 1),
                "end_date": date(2025, 1, 1),
                "excess_spy": 0.02,
                "excess_sector": 0.01,
                "stock_label_skip_reason": None,
            }
        ]
    )
    tickers = ["AAPL", "MSFT"]
    as_of_dates = [date(2020, 1, 1), date(2020, 2, 1)]
    sector_map = {"AAPL": "Technology", "MSFT": "Technology"}

    out, report = build_label_dataset(
        tickers,
        as_of_dates,
        sector_by_ticker=sector_map,
        existing=existing,
        build_fn=_fake_build,
    )

    # Requested 4 pairs, 1 already existed -> attempt 3 new.
    assert report.requested_pairs == 4
    assert report.existing_pairs == 1
    assert report.new_pairs_attempted == 3
    assert report.rows_total == 4
    assert len(out) == 4
    # Existing row remains; new rows added.
    assert set(out["ticker"]) == {"AAPL", "MSFT"}
    assert set(pd.to_datetime(out["as_of"]).dt.date) == {date(2020, 1, 1), date(2020, 2, 1)}


def test_csv_roundtrip_and_loader_helpers(tmp_path: Path) -> None:
    tfile = tmp_path / "tickers.txt"
    tfile.write_text("aapl\nMSFT\n\n", encoding="utf-8")
    assert load_tickers_file(tfile) == ["AAPL", "MSFT"]

    sfile = tmp_path / "sectors.csv"
    sfile.write_text("ticker,sector\nAAPL,Technology\nMSFT,Technology\n", encoding="utf-8")
    assert load_sector_file(sfile) == {"AAPL": "Technology", "MSFT": "Technology"}

    df = pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "as_of": date(2020, 1, 1),
                "end_date": date(2025, 1, 1),
                "excess_spy": 0.1,
                "excess_sector": 0.08,
                "stock_label_skip_reason": None,
            }
        ]
    )
    out = tmp_path / "labels.csv"
    write_label_output(df, out)
    loaded = read_existing_label_output(out)
    assert len(loaded) == 1
    assert loaded.loc[0, "ticker"] == "AAPL"

