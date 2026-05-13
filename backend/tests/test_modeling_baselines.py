from __future__ import annotations

from datetime import date

import pandas as pd

from backend.app.analysis.modeling_baselines import (
    evaluate_baselines,
    infer_feature_columns,
    prepare_training_frame,
    split_by_time,
    top_tercile_hit_rate,
)


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "as_of": date(2018, 1, 1),
                "excess_spy": 0.01,
                "price_ret_12m": 0.05,
                "beta_spy_1y": 0.9,
            },
            {
                "ticker": "BBB",
                "as_of": date(2019, 1, 1),
                "excess_spy": 0.03,
                "price_ret_12m": 0.02,
                "beta_spy_1y": 1.1,
            },
            {
                "ticker": "CCC",
                "as_of": date(2020, 1, 1),
                "excess_spy": -0.02,
                "price_ret_12m": -0.03,
                "beta_spy_1y": 1.2,
            },
            {
                "ticker": "DDD",
                "as_of": date(2021, 1, 1),
                "excess_spy": 0.08,
                "price_ret_12m": 0.10,
                "beta_spy_1y": 0.8,
            },
        ]
    )


def test_prepare_training_frame_and_features() -> None:
    df = prepare_training_frame(_sample_df(), target="excess_spy", date_col="as_of")
    cols = infer_feature_columns(df, "excess_spy")
    assert "price_ret_12m" in cols
    assert "beta_spy_1y" in cols
    assert "ticker" not in cols
    assert "excess_spy" not in cols


def test_split_and_baselines() -> None:
    df = prepare_training_frame(_sample_df(), target="excess_spy", date_col="as_of")
    train, val, test, summary = split_by_time(
        df,
        train_end="2019-12-31",
        val_end="2020-12-31",
        date_col="as_of",
    )
    assert summary.train_rows == 2
    assert summary.val_rows == 1
    assert summary.test_rows == 1
    metrics = evaluate_baselines(train, test, target="excess_spy")
    assert "baseline_constant_median" in metrics
    assert "baseline_momentum" in metrics


def test_top_tercile_hit_rate_bounds() -> None:
    y = pd.Series([0.1, 0.2, 0.3, -0.1, 0.0])
    s = pd.Series([0.1, 0.2, 0.4, -0.2, 0.0])
    h = top_tercile_hit_rate(y, s)
    assert 0.0 <= h <= 1.0

