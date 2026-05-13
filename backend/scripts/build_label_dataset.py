from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.analysis.label_dataset import (
    build_label_dataset,
    generate_as_of_dates,
    load_sector_file,
    load_tickers_file,
    read_existing_label_output,
    write_label_output,
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Phase E: build 5y label rows over a (ticker, as_of) grid."
    )
    p.add_argument("--tickers-file", required=True, help="Path to .txt/.csv with tickers.")
    p.add_argument("--output", required=True, help="Output file path (.csv or .parquet).")
    p.add_argument("--asof-start", required=True, help="Start date (YYYY-MM-DD).")
    p.add_argument("--asof-end", required=True, help="End date (YYYY-MM-DD).")
    p.add_argument(
        "--frequency",
        default="monthly",
        choices=["monthly", "quarterly"],
        help="Grid frequency for as_of dates.",
    )
    p.add_argument(
        "--sector-file",
        default=None,
        help="Optional CSV with ticker,sector columns to avoid yfinance sector lookups.",
    )
    p.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignore existing output; rebuild from scratch.",
    )
    p.add_argument(
        "--no-parent-spy-fill",
        action="store_true",
        help="Disable SPY fallback for missing sector ETF return.",
    )
    p.add_argument(
        "--no-merger-aware",
        action="store_true",
        help="Disable Phase D merger-aware stock label logic.",
    )
    return p.parse_args()


def _to_date(x: str) -> date:
    return date.fromisoformat(x.strip())


def main() -> int:
    args = _parse_args()
    tickers_file = Path(args.tickers_file)
    out_path = Path(args.output)

    tickers = load_tickers_file(tickers_file)
    as_of_dates = generate_as_of_dates(
        _to_date(args.asof_start),
        _to_date(args.asof_end),
        args.frequency,
    )
    sector_map = load_sector_file(Path(args.sector_file)) if args.sector_file else None
    existing = None if args.no_resume else read_existing_label_output(out_path)

    df, report = build_label_dataset(
        tickers,
        as_of_dates,
        sector_by_ticker=sector_map,
        existing=existing,
        use_spy_if_sector_etf_fails=not args.no_parent_spy_fill,
        merger_aware=not args.no_merger_aware,
    )
    write_label_output(df, out_path)

    print(f"wrote: {out_path}")
    print(json.dumps(report.to_dict(), default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

