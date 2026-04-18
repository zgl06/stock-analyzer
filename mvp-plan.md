# Stock Analyzer MVP Plan

## Summary
Build an MVP that proves one workflow end to end: enter a US stock ticker, fetch recent fundamentals and filings, compute a deterministic long-term score plus 3-5 year scenario returns, generate a qualitative summary using local `Qwen2.5-7B-Instruct`, and show the result in a single-stock dashboard. The MVP should run cheaply with `Vercel + Supabase` for the app layer and a separate local inference process for qualitative analysis.

## MVP Scope And Build Order
- **Phase 1: Foundation**
  - Create a monorepo with `Next.js` frontend, `FastAPI` backend, shared environment config, and Supabase integration.
  - Set up `Supabase Postgres` tables for companies, raw filings metadata, normalized financial metrics, analysis jobs, document summaries, and final analysis snapshots.
  - Define the MVP API contract up front:
    - `POST /analyze/{ticker}` to enqueue or refresh analysis
    - `GET /analysis/{ticker}` to fetch the latest result
    - `GET /health` for service readiness
- **Phase 2: Data ingestion**
  - Implement ticker-to-company resolution and SEC CIK lookup.
  - Ingest recent `10-K`, `10-Q`, and relevant `8-K` filing metadata from EDGAR.
  - Pull current price, market cap, sector/industry, and historical price data from a free market-data source.
  - Normalize the core metrics required for the dashboard: revenue, net income, EPS, gross margin, operating margin, free cash flow, debt, cash, shares outstanding, YoY growth, and simple valuation multiples.
- **Phase 3: MVP analysis engine**
  - Implement a deterministic scoring engine with fixed weights for business quality, growth, profitability, balance-sheet strength, and valuation.
  - Implement a 3-scenario return model: `bear`, `base`, and `bull`, producing expected annualized return ranges over 3-5 years.
  - Keep analyst-consensus inputs optional in MVP. If unavailable, use only fundamentals plus peer/valuation assumptions and label consensus as unavailable.
  - Implement a lightweight peer-selection module using sector/industry plus market-cap proximity; return 5 peers maximum in MVP.
- **Phase 4: Qualitative AI layer**
  - Use `Qwen2.5-7B-Instruct` as the default local model for filing and earnings-text interpretation.
  - Use retrieval-first prompts: chunk filings, embed chunks, retrieve only relevant sections, then ask the model for structured output.
  - Limit the MVP qualitative schema to:
    - management tone
    - guidance direction
    - top risks
    - top positives
    - one-paragraph investment thesis
  - Add graceful fallback so the analysis still completes if the model layer is unavailable; the dashboard should show `qualitative summary unavailable` rather than fail.
- **Phase 5: Dashboard**
  - Build one input page with ticker search/submit.
  - Build one stock detail page showing:
    - company snapshot
    - current price and valuation snapshot
    - overall long-term rating
    - expected return range and confidence
    - key financial metrics and trends
    - peer comparison
    - qualitative summary and risks
    - `why this rating` score breakdown
  - Show queued/loading/cached/completed/error states explicitly.
- **Phase 6: Deployment**
  - Deploy frontend and lightweight API routes to `Vercel`.
  - Use `Supabase` for database, auth if needed later, and optional storage for cached documents/results.
  - Keep model inference off-platform: local machine during MVP, with a later option to move to a cheap separate VM or container.
  - Cache completed analyses so repeated ticker views are fast and cheap.

## Important Interfaces And Types
- `POST /analyze/{ticker}`
  - Creates or refreshes an `AnalysisJobStatus` record with `queued | running | completed | failed`
- `GET /analysis/{ticker}`
  - Returns `InvestmentVerdict` plus `CompanySnapshot`, `FinancialSeries`, `ScoreBreakdown`, `ForecastScenario[]`, `PeerComparison[]`, and optional `DocumentSummary`
- Core MVP types:
  - `CompanySnapshot`
  - `NormalizedFinancials`
  - `ScoreBreakdown`
  - `ForecastScenario`
  - `PeerComparison`
  - `DocumentSummary`
  - `InvestmentVerdict`
  - `AnalysisJobStatus`

## Test Plan
- Invalid, delisted, and unsupported tickers return clean validation errors.
- A valid large-cap ticker produces a completed analysis snapshot with all required numeric fields.
- Filing ingestion and normalization correctly populate revenue, net income, EPS, cash, and debt for at least 3 known companies.
- Score calculation is deterministic and stable for the same input snapshot.
- Scenario return math produces sensible outputs and does not emit impossible values.
- Peer selection returns same-industry or clearly adjacent peers and never returns the input company as its own peer.
- Local `Qwen2.5-7B` summaries stay within the fixed schema and never replace numeric source-of-truth values.
- If the model service is offline, the dashboard still renders the numeric analysis and flags missing qualitative output.
- Cached-analysis behavior works end to end: first request queues work, repeat request returns stored results.

## Assumptions And Defaults
- MVP means one excellent single-stock workflow, not a cross-market screener.
- The recommendation is decision support for internal research, not personalized financial advice.
- The rating is produced by deterministic finance logic; the local model is only used for qualitative interpretation and explanation.
- `Qwen2.5-7B-Instruct` is the default local model because it is the most realistic low-cost option for local inference.
- Analyst coverage may be incomplete under free data constraints and should be treated as optional, not required.
- `Vercel + Supabase` host the product layer only; the qualitative model runs separately.
