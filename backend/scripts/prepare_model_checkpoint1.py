from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd

from backend.app.analysis.modeling_baselines import (
    evaluate_baselines,
    infer_feature_columns,
    prepare_training_frame,
    split_by_time,
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Phase G checkpoint 1: prepare dataset, split by time, evaluate baselines."
    )
    p.add_argument("--input", required=True, help="Merged train file (.csv or .parquet).")
    p.add_argument("--target", default="excess_spy", help="Label target column.")
    p.add_argument("--date-col", default="as_of", help="Date column for time split.")
    p.add_argument("--train-end", required=True, help="Train split end date YYYY-MM-DD.")
    p.add_argument("--val-end", required=True, help="Validation split end date YYYY-MM-DD.")
    p.add_argument("--metrics-out", required=True, help="JSON output for metrics/report.")
    p.add_argument(
        "--prepared-out",
        default=None,
        help="Optional path to write prepared rows with split labels.",
    )
    return p.parse_args()


def _read(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, keep_default_na=True)
    if path.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    raise ValueError("input must be .csv or .parquet")


def main() -> int:
    args = _parse_args()
    inp = Path(args.input)
    df0 = _read(inp)
    df = prepare_training_frame(df0, target=args.target, date_col=args.date_col)
    feature_cols = infer_feature_columns(df, args.target)

    train, val, test, split = split_by_time(
        df,
        train_end=args.train_end,
        val_end=args.val_end,
        date_col=args.date_col,
    )
    baselines = evaluate_baselines(train, test, target=args.target)

    report = {
        "input_rows_raw": int(len(df0)),
        "input_rows_after_target_filter": int(len(df)),
        "target": args.target,
        "date_col": args.date_col,
        "split": split.to_dict(),
        "feature_columns_count": len(feature_cols),
        "feature_columns": feature_cols,
        "baselines": baselines,
    }

    out = Path(args.metrics_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote metrics: {out}")
    print(json.dumps(report["split"], indent=2))
    print(json.dumps(report["baselines"], indent=2))

    if args.prepared_out:
        p = Path(args.prepared_out)
        tag_train = train.copy()
        tag_train["split"] = "train"
        tag_val = val.copy()
        tag_val["split"] = "val"
        tag_test = test.copy()
        tag_test["split"] = "test"
        prep = pd.concat([tag_train, tag_val, tag_test], ignore_index=True)
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.suffix.lower() == ".csv":
            prep.to_csv(p, index=False)
        elif p.suffix.lower() in {".parquet", ".pq"}:
            prep.to_parquet(p, index=False)
        else:
            raise ValueError("prepared-out must be .csv or .parquet")
        print(f"wrote prepared: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

