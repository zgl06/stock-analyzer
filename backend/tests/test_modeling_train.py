from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from backend.app.analysis.modeling_train import gate_decision, train_lightgbm_regressor


def _synthetic() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    rows = []
    tickers = [f"T{i:03d}" for i in range(40)]
    dates = pd.date_range("2012-01-01", "2020-12-01", freq="MS")
    for d in dates:
        for t in tickers:
            f1 = rng.normal(0, 1)
            f2 = rng.normal(0, 1)
            noise = rng.normal(0, 0.2)
            y = 0.6 * f1 + 0.25 * f2 + noise
            rows.append(
                {
                    "ticker": t,
                    "as_of": d.date(),
                    "price_ret_12m": f1,
                    "beta_spy_1y": f2,
                    "analyst_count": abs(rng.normal(20, 5)),
                    "excess_spy": y,
                }
            )
    return pd.DataFrame(rows)


def test_gate_decision_threshold() -> None:
    g = gate_decision(
        model_hit_rate=0.45,
        baseline_constant_hit_rate=0.33,
        baseline_momentum_hit_rate=0.36,
        min_uplift=0.03,
    )
    assert g.passed
    assert g.best_baseline_hit_rate == 0.36


def test_train_lightgbm_regressor_smoke() -> None:
    df = _synthetic()
    model, report, preds = train_lightgbm_regressor(
        df,
        target="excess_spy",
        date_col="as_of",
        train_end="2016-12-31",
        val_end="2018-12-31",
        random_state=7,
    )
    assert model is not None
    assert report["target"] == "excess_spy"
    assert report["split"]["train_rows"] > 0
    assert report["split"]["val_rows"] > 0
    assert report["split"]["test_rows"] > 0
    assert "test_metrics" in report
    assert "gate" in report
    assert not preds.empty
    assert {"ticker", "as_of", "y_true", "y_pred"}.issubset(preds.columns)

