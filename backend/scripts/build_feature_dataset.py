from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd

from backend.app.analysis.feature_dataset import (
    build_feature_dataset_from_labels,
    read_existing_feature_output,
    write_feature_output,
)
from backend.app.analysis.label_dataset import read_existing_label_output


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Phase F: build PIT feature rows from Phase E labels."
    )
    p.add_argument("--labels-input", required=True, help="Path to labels .csv/.parquet")
    p.add_argument("--features-output", required=True, help="Output features .csv/.parquet")
    p.add_argument(
        "--merged-output",
        default=None,
        help="Optional merged output (labels join features) .csv/.parquet",
    )
    p.add_argument("--no-resume", action="store_true", help="Ignore existing feature output.")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    labels_path = Path(args.labels_input)
    feat_path = Path(args.features_output)

    labels = read_existing_label_output(labels_path)
    if labels.empty:
        raise SystemExit(f"labels input is empty or missing required rows: {labels_path}")

    existing = None if args.no_resume else read_existing_feature_output(feat_path)
    features, report = build_feature_dataset_from_labels(labels, existing_features=existing)
    write_feature_output(features, feat_path)

    print(f"wrote features: {feat_path}")
    print(json.dumps(report.to_dict(), default=str, indent=2))

    if args.merged_output:
        merged_path = Path(args.merged_output)
        left = labels.copy()
        left["ticker"] = left["ticker"].astype(str).str.upper().str.strip()
        left["as_of"] = pd.to_datetime(left["as_of"]).dt.date
        right = features.copy()
        right["ticker"] = right["ticker"].astype(str).str.upper().str.strip()
        right["as_of"] = pd.to_datetime(right["as_of"]).dt.date
        merged = left.merge(right, on=["ticker", "as_of"], how="left", suffixes=("", "_feat"))
        write_feature_output(merged, merged_path)
        print(f"wrote merged: {merged_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

