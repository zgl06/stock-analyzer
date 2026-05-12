from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.config import get_settings


def _resolve(value: str | None) -> Path | None:
    if not value:
        return None
    p = Path(value)
    if p.is_absolute():
        return p
    return (REPO_ROOT / p).resolve()


def _check_file(path: Path | None) -> dict[str, object]:
    if path is None:
        return {"configured": False, "exists": False, "path": None}
    return {"configured": True, "exists": path.exists(), "path": str(path)}


def main() -> int:
    s = get_settings()
    model_path = _resolve(s.relative_model_path)
    features_path = _resolve(s.relative_model_features_path)
    preds_path = _resolve(s.relative_model_predictions_path)
    sector_model_path = _resolve(s.relative_model_sector_path)
    sector_features_path = _resolve(s.relative_model_sector_features_path)
    sector_preds_path = _resolve(s.relative_model_sector_predictions_path)

    report = {
        "RELATIVE_MODEL_PATH": _check_file(model_path),
        "RELATIVE_MODEL_FEATURES_PATH": _check_file(features_path),
        "RELATIVE_MODEL_PREDICTIONS_PATH": _check_file(preds_path),
        "RELATIVE_MODEL_SECTOR_PATH": _check_file(sector_model_path),
        "RELATIVE_MODEL_SECTOR_FEATURES_PATH": _check_file(sector_features_path),
        "RELATIVE_MODEL_SECTOR_PREDICTIONS_PATH": _check_file(sector_preds_path),
    }

    # Optional schema sanity for feature names JSON
    feature_columns_ok = False
    feature_count = 0
    if features_path and features_path.exists():
        try:
            payload = json.loads(features_path.read_text(encoding="utf-8"))
            cols = payload.get("feature_columns", [])
            feature_columns_ok = isinstance(cols, list) and len(cols) > 0
            feature_count = len(cols) if isinstance(cols, list) else 0
        except Exception:
            feature_columns_ok = False
    report["feature_columns_ok"] = feature_columns_ok
    report["feature_columns_count"] = feature_count

    sector_feature_columns_ok = False
    sector_feature_count = 0
    if sector_features_path and sector_features_path.exists():
        try:
            payload = json.loads(sector_features_path.read_text(encoding="utf-8"))
            cols = payload.get("feature_columns", [])
            sector_feature_columns_ok = isinstance(cols, list) and len(cols) > 0
            sector_feature_count = len(cols) if isinstance(cols, list) else 0
        except Exception:
            sector_feature_columns_ok = False
    report["sector_feature_columns_ok"] = sector_feature_columns_ok
    report["sector_feature_columns_count"] = sector_feature_count

    print(json.dumps(report, indent=2))

    ok = (
        bool(report["RELATIVE_MODEL_PATH"]["exists"])
        and bool(report["RELATIVE_MODEL_FEATURES_PATH"]["exists"])
        and feature_columns_ok
        and bool(report["RELATIVE_MODEL_SECTOR_PATH"]["exists"])
        and bool(report["RELATIVE_MODEL_SECTOR_FEATURES_PATH"]["exists"])
        and sector_feature_columns_ok
    )
    # predictions path is recommended but not mandatory for inference.
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

