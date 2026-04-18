# Stock Analyzer v1 Plan

## Summary
Build a full-stack web app for an internal research workflow that analyzes a single ticker deeply and explains whether it looks attractive for a 3-5 year holding period. The system will use SEC filings as the primary source of truth, supplement with free market-data sources for price/sector/peer context, and combine deterministic scoring with LLM-generated qualitative document summaries. v1 is a decision-support product, not an autonomous trading model.

## Implementation Changes
- **Architecture**
  - Use a two-part app: `Next.js` frontend for the dashboard and input flow, plus a `Python FastAPI` analysis service for financial-data ingestion, scoring, and forecasting.
  - Keep the repo as a monorepo with one shared config layer and a simple job queue pattern for longer analyses.
  - Store normalized company snapshots, filing-derived metrics, peer sets, score outputs, and cached LLM summaries in `Postgres`.
- **Core analysis pipeline**
  - Accept a ticker input, resolve the company/CIK, fetch recent SEC filings (`10-K`, `10-Q`, `8-K` earnings items when available), and extract or normalize core metrics: revenue, net income, EPS, gross margin, operating margin, free cash flow, debt, cash, shares outstanding, growth rates.
  - Pull free market and metadata inputs for current price, market cap, sector/industry tags, basic analyst consensus if available, and historical price performance. Default provider mix: SEC EDGAR for filings, Yahoo Finance or `yfinance` for market data, and a free-tier source such as Finnhub only where needed for profile/peer metadata.
  - Build a peer-discovery module using sector/industry classification first, then refine peers by size and business similarity. Show 5-10 peers and compare growth, margins, valuation multiples, and recent performance.
  - Add an LLM-based document layer that summarizes the latest filing and earnings commentary into a fixed schema: management tone, guidance direction, major risks, capital-allocation signals, and notable changes vs prior period. Numeric values remain sourced from structured extraction only.
- **Scoring, forecast, and recommendation**
  - Implement an explainable composite rating, not a black-box model. Use weighted pillars: business quality, growth, profitability, balance-sheet strength, valuation, estimate/revision context, and qualitative management/risk signals.
  - Produce a `LongTermRating` such as `Strong Buy`, `Buy`, `Hold`, `Avoid` from score thresholds, plus a confidence band driven by data completeness and signal agreement.
  - Forecast expected 3-5 year return using scenario analysis instead of direct price prediction: revenue growth path, margin path, EPS/FCF path, and terminal valuation multiple. Use `base`, `bull`, and `bear` scenarios.
  - Blend analyst sentiment only as one input. If analyst-target coverage is sparse under free data limits, fall back to “market-implied + peer-multiple” scenarios and mark analyst consensus as unavailable rather than inventing it.
- **Dashboard UX**
  - Main flow: enter ticker, run analysis, land on a single-stock dashboard.
  - Dashboard sections: price snapshot, overall rating, expected annualized return range, confidence, thesis summary, key financial metrics, trend charts, filing/earnings summary, peer comparison table, valuation/scenario model, and portfolio-fit conclusion for long-term investors.
  - Include explicit explanations for every score component and a “why this rating” panel so the result is auditable.
- **Public interfaces**
  - `POST /analyze/{ticker}`: run or refresh a full analysis.
  - `GET /analysis/{ticker}`: return latest normalized analysis payload.
  - `GET /peers/{ticker}`: return peer list and comparison metrics.
  - Core response types should include `CompanySnapshot`, `FinancialSeries`, `PeerComparison`, `DocumentSummary`, `ScoreBreakdown`, `ForecastScenario`, and `InvestmentVerdict`.
- **Modeling defaults**
  - Start with deterministic weighted scoring plus scenario valuation; do not plan a training-heavy ML ranking model in v1.
  - Design the pipeline so a later v2 can add a learned ranking model using stored historical features and realized returns without changing the dashboard contract.

## Test Plan
- Ticker resolution works for common US equities and rejects invalid/delisted symbols cleanly.
- Filing ingestion correctly populates revenue, net income, EPS, and cash/debt fields for at least large-cap and mid-cap examples.
- Peer selection returns sensible same-industry companies and avoids obviously unrelated firms.
- Score output is stable and explainable when some external fields are missing.
- Forecast scenarios produce bounded, non-nonsensical outputs and annualized return math is correct.
- LLM summaries follow the fixed schema, never overwrite structured numeric truth, and degrade gracefully if the LLM call fails.
- Dashboard renders loading, success, stale-cache, and no-data states clearly.

## Assumptions And Defaults
- v1 is for internal use, so compliance language can be lighter, but the UI should still state this is research support and not personalized financial advice.
- The project should optimize for free data sources first; missing analyst-consensus coverage is acceptable if the app labels it transparently.
- LLM use is limited to qualitative summaries and explanations; the investment rating itself is produced by deterministic scoring plus scenario analysis.
- Default stack choice is `Next.js + FastAPI + Postgres` because it keeps the UI/product layer clean while making financial-data processing easier in Python.
- v1 prioritizes one excellent single-stock page; a market-wide screener is deferred until the core analysis schema and scoring engine are stable.
