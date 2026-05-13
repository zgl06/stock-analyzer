from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.analysis.modeling_train import train_lightgbm_regressor


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Phase G checkpoint 2: train LightGBM and export artifacts."
    )
    p.add_argument("--input", required=True, help="Merged train file (.csv or .parquet).")
    p.add_argument("--target", default="excess_spy", help="Target label column.")
    p.add_argument("--date-col", default="as_of", help="Date column for time split.")
    p.add_argument("--train-end", required=True, help="Train split end date YYYY-MM-DD.")
    p.add_argument("--val-end", required=True, help="Validation split end date YYYY-MM-DD.")
    p.add_argument("--model-out", required=True, help="Path to save LightGBM model (.txt).")
    p.add_argument("--metrics-out", required=True, help="Path to save metrics JSON.")
    p.add_argument(
        "--feature-names-out",
        default=None,
        help="Optional path to save feature names JSON.",
    )
    p.add_argument(
        "--predictions-out",
        default=None,
        help="Optional path to save test predictions CSV/Parquet.",
    )
    p.add_argument("--random-state", type=int, default=42)
    return p.parse_args()


def _read(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, keep_default_na=True)
    if path.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    raise ValueError("input must be .csv or .parquet")


def main() -> int:
    args = _parse_args()
    df = _read(Path(args.input))
    model, report, preds = train_lightgbm_regressor(
        df,
        target=args.target,
        date_col=args.date_col,
        train_end=args.train_end,
        val_end=args.val_end,
        random_state=args.random_state,
    )

    model_out = Path(args.model_out)
    model_out.parent.mkdir(parents=True, exist_ok=True)
    model.booster_.save_model(str(model_out))

    metrics_out = Path(args.metrics_out)
    metrics_out.parent.mkdir(parents=True, exist_ok=True)
    metrics_out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.feature_names_out:
        fno = Path(args.feature_names_out)
        fno.parent.mkdir(parents=True, exist_ok=True)
        payload = {"feature_columns": report["feature_columns"]}
        fno.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if args.predictions_out:
        po = Path(args.predictions_out)
        po.parent.mkdir(parents=True, exist_ok=True)
        if po.suffix.lower() == ".csv":
            preds.to_csv(po, index=False)
        elif po.suffix.lower() in {".parquet", ".pq"}:
            preds.to_parquet(po, index=False)
        else:
            raise ValueError("predictions-out must be .csv or .parquet")

    print(f"wrote model: {model_out}")
    print(f"wrote metrics: {metrics_out}")
    print(json.dumps(report["split"], indent=2))
    print(json.dumps(report["test_metrics"], indent=2))
    print(json.dumps(report["gate"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

