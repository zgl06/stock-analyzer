from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.analysis.feature_dataset import (
    build_feature_dataset_from_labels,
    read_existing_feature_output,
    write_feature_output,
)
from backend.app.analysis.label_dataset import (
    build_label_dataset,
    generate_as_of_dates,
    read_existing_label_output,
    write_label_output,
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Run full flow through Phase F for one ticker: "
            "build labels (Phase E), build features (Phase F), and write compiled merged file."
        )
    )
    p.add_argument("--ticker", required=True, help="Single ticker, e.g. AAPL")
    p.add_argument(
        "--compiled-output",
        required=True,
        help="Merged labels+features output (.csv or .parquet).",
    )
    p.add_argument(
        "--labels-output",
        default=None,
        help="Optional labels output path; defaults next to compiled output.",
    )
    p.add_argument(
        "--features-output",
        default=None,
        help="Optional features output path; defaults next to compiled output.",
    )
    p.add_argument("--asof-start", default="2010-01-01", help="YYYY-MM-DD")
    p.add_argument("--asof-end", default="2018-12-31", help="YYYY-MM-DD")
    p.add_argument(
        "--frequency",
        default="monthly",
        choices=["monthly", "quarterly"],
        help="as_of grid frequency",
    )
    p.add_argument(
        "--sector",
        default=None,
        help="Optional sector override string (e.g. Technology).",
    )
    p.add_argument(
        "--no-resume",
        action="store_true",
        help="Do not resume from existing labels/features outputs.",
    )
    p.add_argument(
        "--no-parent-spy-fill",
        action="store_true",
        help="Disable SPY fallback for missing sector ETF return.",
    )
    p.add_argument(
        "--no-merger-aware",
        action="store_true",
        help="Disable merger-aware stock label logic.",
    )
    return p.parse_args()


def _to_date(x: str) -> date:
    return date.fromisoformat(x.strip())


def _default_output_paths(compiled_out: Path) -> tuple[Path, Path]:
    stem = compiled_out.stem
    suffix = compiled_out.suffix or ".csv"
    labels = compiled_out.with_name(f"{stem}_labels{suffix}")
    features = compiled_out.with_name(f"{stem}_features{suffix}")
    return labels, features


def main() -> int:
    args = _parse_args()

    ticker = args.ticker.strip().upper()
    if not ticker:
        raise SystemExit("ticker is required")

    compiled_out = Path(args.compiled_output)
    labels_default, features_default = _default_output_paths(compiled_out)
    labels_out = Path(args.labels_output) if args.labels_output else labels_default
    features_out = Path(args.features_output) if args.features_output else features_default

    as_of_dates = generate_as_of_dates(
        _to_date(args.asof_start),
        _to_date(args.asof_end),
        args.frequency,
    )
    sector_map = {ticker: args.sector.strip()} if args.sector and args.sector.strip() else None

    existing_labels = None if args.no_resume else read_existing_label_output(labels_out)
    labels_df, labels_report = build_label_dataset(
        [ticker],
        as_of_dates,
        sector_by_ticker=sector_map,
        existing=existing_labels,
        use_spy_if_sector_etf_fails=not args.no_parent_spy_fill,
        merger_aware=not args.no_merger_aware,
    )
    write_label_output(labels_df, labels_out)

    existing_features = None if args.no_resume else read_existing_feature_output(features_out)
    features_df, features_report = build_feature_dataset_from_labels(
        labels_df,
        existing_features=existing_features,
    )
    write_feature_output(features_df, features_out)

    left = labels_df.copy()
    left["ticker"] = left["ticker"].astype(str).str.upper().str.strip()
    left["as_of"] = pd.to_datetime(left["as_of"]).dt.date
    right = features_df.copy()
    right["ticker"] = right["ticker"].astype(str).str.upper().str.strip()
    right["as_of"] = pd.to_datetime(right["as_of"]).dt.date
    merged = left.merge(right, on=["ticker", "as_of"], how="left", suffixes=("", "_feat"))
    write_feature_output(merged, compiled_out)

    print(f"ticker: {ticker}")
    print(f"wrote labels:   {labels_out}")
    print(f"wrote features: {features_out}")
    print(f"wrote compiled: {compiled_out}")
    print("labels_report:")
    print(json.dumps(labels_report.to_dict(), default=str, indent=2))
    print("features_report:")
    print(json.dumps(features_report.to_dict(), default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

