"""Phase G checkpoint 2: train/evaluate LightGBM and export artifacts."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from backend.app.analysis.modeling_baselines import (
    evaluate_baselines,
    infer_feature_columns,
    prepare_training_frame,
    split_by_time,
    top_tercile_hit_rate,
)


@dataclass(frozen=True, slots=True)
class GateDecision:
    passed: bool
    reason: str
    model_hit_rate: float
    best_baseline_hit_rate: float
    required_min_uplift: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _decile_spread(y_true: pd.Series, y_score: pd.Series) -> float | None:
    if len(y_true) < 20:
        return None
    tmp = pd.DataFrame({"y_true": y_true.to_numpy(), "y_score": y_score.to_numpy()})
    # rank-based deciles avoid duplicate-bin errors
    pct = tmp["y_score"].rank(method="average", pct=True)
    dec = np.ceil(pct * 10).clip(1, 10).astype(int)
    tmp["decile"] = dec
    top = tmp[tmp["decile"] == 10]["y_true"]
    bot = tmp[tmp["decile"] == 1]["y_true"]
    if top.empty or bot.empty:
        return None
    return float(top.mean() - bot.mean())


def evaluate_model_metrics(y_true: pd.Series, y_pred: pd.Series) -> dict[str, object]:
    y_true = y_true.astype(float).reset_index(drop=True)
    y_pred = y_pred.astype(float).reset_index(drop=True)

    hit = float(top_tercile_hit_rate(y_true, y_pred))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    mae = float(np.mean(np.abs(y_true - y_pred)))
    sp = float(y_true.corr(y_pred, method="spearman")) if len(y_true) > 1 else float("nan")
    spread = _decile_spread(y_true, y_pred)
    return {
        "top_tercile_hit_rate": hit,
        "rmse": rmse,
        "mae": mae,
        "spearman": sp,
        "decile_spread_top_minus_bottom": spread,
    }


def gate_decision(
    *,
    model_hit_rate: float,
    baseline_constant_hit_rate: float,
    baseline_momentum_hit_rate: float,
    min_uplift: float = 0.03,
) -> GateDecision:
    best_baseline = max(baseline_constant_hit_rate, baseline_momentum_hit_rate)
    uplift = model_hit_rate - best_baseline
    passed = bool(uplift >= min_uplift)
    reason = (
        f"model beats best baseline by {uplift:.4f} (>= {min_uplift:.4f})"
        if passed
        else f"model uplift {uplift:.4f} below threshold {min_uplift:.4f}"
    )
    return GateDecision(
        passed=passed,
        reason=reason,
        model_hit_rate=float(model_hit_rate),
        best_baseline_hit_rate=float(best_baseline),
        required_min_uplift=float(min_uplift),
    )


def train_lightgbm_regressor(
    df: pd.DataFrame,
    *,
    target: str,
    date_col: str,
    train_end: str,
    val_end: str,
    random_state: int = 42,
) -> tuple[LGBMRegressor, dict[str, object], pd.DataFrame]:
    """Train LightGBM on train split, early-stop on val, score test split."""
    prepared = prepare_training_frame(df, target=target, date_col=date_col)
    feature_cols = infer_feature_columns(prepared, target)
    train, val, test, split = split_by_time(
        prepared, train_end=train_end, val_end=val_end, date_col=date_col
    )
    if train.empty or val.empty or test.empty:
        raise ValueError("train/val/test split has empty segment; adjust split dates")
    if not feature_cols:
        raise ValueError("No numeric feature columns inferred")

    X_train = train[feature_cols]
    y_train = train[target].astype(float)
    X_val = val[feature_cols]
    y_val = val[target].astype(float)
    X_test = test[feature_cols]
    y_test = test[target].astype(float).reset_index(drop=True)

    model = LGBMRegressor(
        n_estimators=800,
        learning_rate=0.03,
        num_leaves=31,
        max_depth=-1,
        subsample=0.9,
        colsample_bytree=0.9,
        reg_lambda=1.0,
        random_state=random_state,
    )
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        eval_metric="l2",
    )

    pred_test = pd.Series(model.predict(X_test), dtype=float)
    test_metrics = evaluate_model_metrics(y_test, pred_test)
    baselines = evaluate_baselines(train, test, target=target)
    gate = gate_decision(
        model_hit_rate=float(test_metrics["top_tercile_hit_rate"]),
        baseline_constant_hit_rate=float(
            baselines["baseline_constant_median"]["top_tercile_hit_rate"]  # type: ignore[index]
        ),
        baseline_momentum_hit_rate=float(
            baselines["baseline_momentum"]["top_tercile_hit_rate"]  # type: ignore[index]
        ),
    )

    fi_gain = model.booster_.feature_importance(importance_type="gain")
    fi_split = model.booster_.feature_importance(importance_type="split")
    feature_importance = [
        {
            "feature": f,
            "gain": float(g),
            "split": int(s),
        }
        for f, g, s in zip(feature_cols, fi_gain, fi_split, strict=True)
    ]
    feature_importance.sort(key=lambda r: r["gain"], reverse=True)

    report: dict[str, object] = {
        "target": target,
        "date_col": date_col,
        "split": split.to_dict(),
        "feature_columns_count": len(feature_cols),
        "feature_columns": feature_cols,
        "test_metrics": test_metrics,
        "baselines": baselines,
        "gate": gate.to_dict(),
        "feature_importance_top25": feature_importance[:25],
        "best_iteration_": int(getattr(model, "best_iteration_", 0) or 0),
    }

    preds = test[["ticker", date_col, target]].copy()
    preds = preds.rename(columns={target: "y_true"})
    preds["y_pred"] = pred_test.to_numpy()
    return model, report, preds

