"""Phase G checkpoint 1: dataset prep, time split, and baseline metrics."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


NON_FEATURE_COLUMNS = {
    "ticker",
    "as_of",
    "end_date",
    "gics_or_vendor",
    "sector_bench_ticker",
    "parent_spy_filled",
    "mapped_sector_etf",
    "stock_label_symbol",
    "stock_label_skip_reason",
    "stock_label_merger_note",
    "r_stock_5y",
    "r_spy_5y",
    "r_sector_5y",
    "excess_spy",
    "excess_sector",
}


@dataclass(frozen=True, slots=True)
class SplitSummary:
    train_rows: int
    val_rows: int
    test_rows: int
    train_end: str
    val_end: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def infer_feature_columns(df: pd.DataFrame, target: str) -> list[str]:
    cols: list[str] = []
    for c in df.columns:
        if c in NON_FEATURE_COLUMNS or c == target:
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            cols.append(c)
    return sorted(cols)


def prepare_training_frame(
    df: pd.DataFrame,
    *,
    target: str,
    date_col: str = "as_of",
) -> pd.DataFrame:
    if target not in df.columns:
        raise ValueError(f"target column not found: {target}")
    if date_col not in df.columns:
        raise ValueError(f"date column not found: {date_col}")
    out = df.copy()
    out["ticker"] = out["ticker"].astype(str).str.upper().str.strip()
    out[date_col] = pd.to_datetime(out[date_col]).dt.date
    out = out.dropna(subset=[target])
    out = out.sort_values([date_col, "ticker"]).reset_index(drop=True)
    return out


def split_by_time(
    df: pd.DataFrame,
    *,
    train_end: str,
    val_end: str,
    date_col: str = "as_of",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, SplitSummary]:
    te = pd.to_datetime(train_end).date()
    ve = pd.to_datetime(val_end).date()
    if ve <= te:
        raise ValueError("val_end must be after train_end")
    train = df[df[date_col] <= te].copy()
    val = df[(df[date_col] > te) & (df[date_col] <= ve)].copy()
    test = df[df[date_col] > ve].copy()
    summary = SplitSummary(
        train_rows=len(train),
        val_rows=len(val),
        test_rows=len(test),
        train_end=str(te),
        val_end=str(ve),
    )
    return train, val, test, summary


def top_tercile_hit_rate(y_true: pd.Series, y_score: pd.Series) -> float:
    """Hit rate of predicted top tercile vs realized top tercile."""
    n = len(y_true)
    if n == 0:
        return float("nan")
    k = max(1, int(np.ceil(n / 3.0)))
    order_pred = np.argsort(-y_score.to_numpy())
    order_true = np.argsort(-y_true.to_numpy())
    pred_top = set(order_pred[:k].tolist())
    true_top = set(order_true[:k].tolist())
    hits = len(pred_top & true_top)
    return hits / k


def evaluate_baselines(
    train: pd.DataFrame,
    test: pd.DataFrame,
    *,
    target: str,
) -> dict[str, object]:
    if test.empty:
        raise ValueError("test split is empty; adjust split dates")
    y_test = test[target].astype(float).reset_index(drop=True)

    # Baseline A: constant median from training target.
    med = float(train[target].median()) if not train.empty else float(y_test.median())
    score_const = pd.Series([med] * len(test), dtype=float)
    hit_const = top_tercile_hit_rate(y_test, score_const)

    # Baseline B: 12m momentum if present, else 3m, else constant.
    if "price_ret_12m" in test.columns:
        score_mom = pd.to_numeric(test["price_ret_12m"], errors="coerce")
    elif "price_ret_3m" in test.columns:
        score_mom = pd.to_numeric(test["price_ret_3m"], errors="coerce")
    else:
        score_mom = score_const.copy()
    score_mom = score_mom.fillna(score_mom.median() if score_mom.notna().any() else med)
    hit_mom = top_tercile_hit_rate(y_test, score_mom.reset_index(drop=True))

    random_expected = 1.0 / 3.0
    out = {
        "target": target,
        "test_rows": int(len(test)),
        "test_target_mean": float(y_test.mean()),
        "baseline_constant_median": {
            "train_target_median": med,
            "top_tercile_hit_rate": float(hit_const),
        },
        "baseline_momentum": {
            "score_col_used": "price_ret_12m" if "price_ret_12m" in test.columns else (
                "price_ret_3m" if "price_ret_3m" in test.columns else "constant_median"
            ),
            "top_tercile_hit_rate": float(hit_mom),
        },
        "random_reference": {
            "expected_top_tercile_hit_rate": random_expected,
        },
    }
    return out

