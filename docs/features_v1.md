# Features v1 (Phase F)

This file documents the first point-in-time feature set built from `(ticker, as_of)` keys.

## Key columns

- `ticker`, `as_of` (join keys)
- Price/market features:
  - `price_close`
  - `price_ret_1m`, `price_ret_3m`, `price_ret_6m`, `price_ret_12m`
  - `price_momentum_12m_minus_1m`
  - `volatility_3m_ann`
  - `max_drawdown_1y`
  - `beta_spy_1y`
- Snapshot valuation / analyst features (free-data best effort):
  - `market_cap_usd`
  - `trailing_pe`
  - `price_to_sales`
  - `analyst_count`
  - `analyst_target_mean_price`
  - `analyst_recommendation_mean`
- Fundamental features (latest period_end <= as_of from normalized financials):
  - `revenue_yoy_growth`
  - `net_income_yoy_growth`
  - `gross_margin`
  - `operating_margin`
  - `debt_to_cash`
  - `fcf_margin`

## Point-in-time policy

- Price features use only closes on or before `as_of`.
- Fundamental snapshot uses the latest normalized financial period where `period_end <= as_of`.
- Analyst/valuation fields are provider snapshot fields and may not be strict point-in-time history with free data.

## Known limitations

- Free provider coverage can be sparse/unstable for analyst fields.
- Statement restatements and filing-lag effects are not fully modeled in v1.
- `beta_spy_1y` requires enough overlapping daily returns; missing values are expected in short histories.

