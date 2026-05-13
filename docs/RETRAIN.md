# Relative Model Retrain Runbook (Phase I)

This runbook covers the **tabular relative model** retrain loop (not LLM prompt/SFT ops).

## Scope

- Models: LightGBM regressors for both `excess_spy` and `excess_sector`.
- Primary acceptance metric: **top-tercile hit rate** on out-of-time test split.
- Gate: model must beat best baseline by minimum uplift (`0.03` default in code).

## Prerequisites

- Label+feature merged dataset exists (for example `backend/outputs/train_5y.csv`).
- Dependencies installed (`lightgbm`, `scikit-learn`, `pandas`, `numpy`).
- Split dates chosen (`train_end`, `val_end`) and documented.

## One-command retrain

```powershell
python backend/scripts/retrain_relative_model.py --input backend/outputs/train_5y.csv --targets excess_spy,excess_sector --date-col as_of --train-end 2015-12-31 --val-end 2017-12-31 --artifact-root backend/outputs/releases --tag prod_candidate
```

Outputs under a versioned directory:

- `excess_spy_model.txt`
- `excess_spy_metrics.json`
- `excess_spy_feature_names.json`
- `excess_spy_test_predictions.csv`
- `excess_sector_model.txt`
- `excess_sector_metrics.json`
- `excess_sector_feature_names.json`
- `excess_sector_test_predictions.csv`
- `run_meta.json` (includes deploy env snippet)

## Quick checklist

- [ ] Rebuild or refresh `train_5y` input (labels + features merged).
- [ ] Run `retrain_relative_model.py` with documented split dates.
- [ ] Confirm gate in output is `passed=true`.
- [ ] Promote or select release directory for deployment.
- [ ] Update `backend/.env` with matching SPY and sector model paths.
- [ ] Run env validator before restart.
- [ ] Restart backend and verify `/analysis/AAPL/relative-model`.

## Deploy the chosen model

Pick a run directory and set in `backend/.env`:

```env
RELATIVE_MODEL_PATH=<path-to-run>/excess_spy_model.txt
RELATIVE_MODEL_FEATURES_PATH=<path-to-run>/excess_spy_feature_names.json
RELATIVE_MODEL_PREDICTIONS_PATH=<path-to-run>/excess_spy_test_predictions.csv
RELATIVE_MODEL_SECTOR_PATH=<path-to-run>/excess_sector_model.txt
RELATIVE_MODEL_SECTOR_FEATURES_PATH=<path-to-run>/excess_sector_feature_names.json
RELATIVE_MODEL_SECTOR_PREDICTIONS_PATH=<path-to-run>/excess_sector_test_predictions.csv
```

Restart backend, then verify:

- `GET /analysis/AAPL/relative-model` returns `vs_spy.methodology = "lightgbm"`.
- `GET /analysis/AAPL/relative-model` returns `vs_sector.methodology = "lightgbm"` for known mapped sectors.
- UI model panel renders score/tercile.

Optional helper to validate env file paths before restart:

```powershell
python backend/scripts/validate_relative_model_env.py
```

Optional helper to promote a release and print env snippet:

```powershell
python backend/scripts/promote_relative_model.py --run-dir backend/outputs/releases/<run_name>
```

## Release checklist

- Gate in `metrics.json` is `passed=true`.
- Test split row count is non-trivial (not tiny).
- No obvious leakage changes in feature list.
- Model beats both baselines on top-tercile hit rate.
- SPY and sector artifact paths are from the **same run**.

## Cadence (default)

- Recompute labels/features monthly or quarterly.
- Retrain after each data refresh.
- Keep at least the last 3 successful release directories for rollback.

## Rollback

If production behavior degrades:

1. Point all six model env vars back to previous run directory.
2. Restart backend.
3. Confirm endpoint and UI recover.

## Notes

- This runbook is for tabular model operations only.
- LLM prompt/SFT operations should be tracked separately (Phase L4).

