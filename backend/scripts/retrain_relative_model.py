from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.analysis.modeling_train import train_lightgbm_regressor


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Phase I retrain runner: train LightGBM, write versioned artifacts, "
            "and print env vars for serving."
        )
    )
    p.add_argument("--input", required=True, help="Merged train file (.csv/.parquet).")
    p.add_argument(
        "--targets",
        default="excess_spy,excess_sector",
        help="Comma-separated targets to train (e.g. excess_spy,excess_sector).",
    )
    p.add_argument("--date-col", default="as_of", help="Date column for time split.")
    p.add_argument("--train-end", required=True, help="Train split end (YYYY-MM-DD).")
    p.add_argument("--val-end", required=True, help="Validation split end (YYYY-MM-DD).")
    p.add_argument(
        "--artifact-root",
        default="backend/outputs/releases",
        help="Root directory for versioned retrain outputs.",
    )
    p.add_argument(
        "--tag",
        default=None,
        help="Optional run tag suffix (e.g. v2); timestamp is always included.",
    )
    p.add_argument("--random-state", type=int, default=42)
    return p.parse_args()


def _read(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, keep_default_na=True)
    if path.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    raise ValueError("input must be .csv or .parquet")


def _run_name(tag: str | None) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    return f"{ts}_{tag}" if tag else ts


def main() -> int:
    args = _parse_args()
    df = _read(Path(args.input))
    targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    if not targets:
        raise SystemExit("No targets provided via --targets")

    run_name = _run_name(args.tag)
    run_dir = (REPO_ROOT / args.artifact_root / run_name).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    trained: dict[str, dict[str, str | dict[str, object]]] = {}
    primary = targets[0]
    for target in targets:
        model, report, preds = train_lightgbm_regressor(
            df,
            target=target,
            date_col=args.date_col,
            train_end=args.train_end,
            val_end=args.val_end,
            random_state=args.random_state,
        )
        model_path = run_dir / f"{target}_model.txt"
        metrics_path = run_dir / f"{target}_metrics.json"
        features_path = run_dir / f"{target}_feature_names.json"
        preds_path = run_dir / f"{target}_test_predictions.csv"
        model.booster_.save_model(str(model_path))
        metrics_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        features_path.write_text(
            json.dumps({"feature_columns": report["feature_columns"]}, indent=2),
            encoding="utf-8",
        )
        preds.to_csv(preds_path, index=False)
        trained[target] = {
            "gate": report.get("gate", {}),
            "model": str(model_path),
            "metrics": str(metrics_path),
            "feature_names": str(features_path),
            "test_predictions": str(preds_path),
        }
    meta_path = run_dir / "run_meta.json"

    meta = {
        "run_name": run_name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "input": str(Path(args.input)),
        "targets": targets,
        "date_col": args.date_col,
        "train_end": args.train_end,
        "val_end": args.val_end,
        "random_state": args.random_state,
        "trained": trained,
        "env_snippet": {
            "RELATIVE_MODEL_PATH": trained.get(primary, {}).get("model"),
            "RELATIVE_MODEL_FEATURES_PATH": trained.get(primary, {}).get("feature_names"),
            "RELATIVE_MODEL_PREDICTIONS_PATH": trained.get(primary, {}).get("test_predictions"),
            "RELATIVE_MODEL_SECTOR_PATH": trained.get("excess_sector", {}).get("model"),
            "RELATIVE_MODEL_SECTOR_FEATURES_PATH": trained.get("excess_sector", {}).get(
                "feature_names"
            ),
            "RELATIVE_MODEL_SECTOR_PREDICTIONS_PATH": trained.get("excess_sector", {}).get(
                "test_predictions"
            ),
        },
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"retrain run: {run_name}")
    print(f"artifact dir: {run_dir}")
    print("gates:")
    print(json.dumps({k: v.get("gate", {}) for k, v in trained.items()}, indent=2))
    print("set these in backend/.env:")
    print(f"RELATIVE_MODEL_PATH={meta['env_snippet']['RELATIVE_MODEL_PATH']}")
    print(
        f"RELATIVE_MODEL_FEATURES_PATH={meta['env_snippet']['RELATIVE_MODEL_FEATURES_PATH']}"
    )
    print(
        f"RELATIVE_MODEL_PREDICTIONS_PATH={meta['env_snippet']['RELATIVE_MODEL_PREDICTIONS_PATH']}"
    )
    if meta["env_snippet"]["RELATIVE_MODEL_SECTOR_PATH"]:
        print(
            f"RELATIVE_MODEL_SECTOR_PATH={meta['env_snippet']['RELATIVE_MODEL_SECTOR_PATH']}"
        )
        print(
            "RELATIVE_MODEL_SECTOR_FEATURES_PATH="
            f"{meta['env_snippet']['RELATIVE_MODEL_SECTOR_FEATURES_PATH']}"
        )
        print(
            "RELATIVE_MODEL_SECTOR_PREDICTIONS_PATH="
            f"{meta['env_snippet']['RELATIVE_MODEL_SECTOR_PREDICTIONS_PATH']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

