from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Promote a release directory by writing a stable 'current' pointer JSON "
            "and printing env vars."
        )
    )
    p.add_argument(
        "--run-dir",
        required=True,
        help=(
            "Path to a release dir containing both bundles: "
            "excess_spy_* and excess_sector_* artifacts."
        ),
    )
    p.add_argument(
        "--pointer-file",
        default="backend/outputs/releases/current.json",
        help="Path to write the stable pointer JSON.",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = (REPO_ROOT / run_dir).resolve()

    model = run_dir / "excess_spy_model.txt"
    features = run_dir / "excess_spy_feature_names.json"
    preds = run_dir / "excess_spy_test_predictions.csv"
    sector_model = run_dir / "excess_sector_model.txt"
    sector_features = run_dir / "excess_sector_feature_names.json"
    sector_preds = run_dir / "excess_sector_test_predictions.csv"
    required = (model, features, preds, sector_model, sector_features, sector_preds)
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise SystemExit(f"cannot promote; missing files:\n- " + "\n- ".join(missing))

    pointer = Path(args.pointer_file)
    if not pointer.is_absolute():
        pointer = (REPO_ROOT / pointer).resolve()
    pointer.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "promoted_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(run_dir),
        "env": {
            "RELATIVE_MODEL_PATH": str(model),
            "RELATIVE_MODEL_FEATURES_PATH": str(features),
            "RELATIVE_MODEL_PREDICTIONS_PATH": str(preds),
            "RELATIVE_MODEL_SECTOR_PATH": str(sector_model),
            "RELATIVE_MODEL_SECTOR_FEATURES_PATH": str(sector_features),
            "RELATIVE_MODEL_SECTOR_PREDICTIONS_PATH": str(sector_preds),
        },
    }
    pointer.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"wrote pointer: {pointer}")
    print("set these in backend/.env:")
    print(f"RELATIVE_MODEL_PATH={model}")
    print(f"RELATIVE_MODEL_FEATURES_PATH={features}")
    print(f"RELATIVE_MODEL_PREDICTIONS_PATH={preds}")
    print(f"RELATIVE_MODEL_SECTOR_PATH={sector_model}")
    print(f"RELATIVE_MODEL_SECTOR_FEATURES_PATH={sector_features}")
    print(f"RELATIVE_MODEL_SECTOR_PREDICTIONS_PATH={sector_preds}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

