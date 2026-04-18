# Stock Analyzer v1 Plan

## Summary
Build a full-stack web app for an internal research workflow that analyzes a single ticker deeply and explains whether it looks attractive for a 3-5 year holding period. The system will use SEC filings as the primary source of truth, supplement with free market-data sources for price/sector/peer context, and combine deterministic scoring with low-cost local qualitative analysis. v1 is a decision-support product, not an autonomous trading model, and it is designed to deploy cheaply on `Vercel + Supabase` with model inference kept separate.

## Implementation Changes
- **Architecture**
  - Use a two-part app: `Next.js` frontend on Vercel and a `Python FastAPI` analysis service for financial-data ingestion, scoring, and forecasting.
  - Keep the repo as a monorepo with one shared config layer and a simple async job pattern for longer analyses.
  - Store normalized company snapshots, filing-derived metrics, peer sets, score outputs, cached model summaries, and job status in `Supabase Postgres`.
- **Free-tier deployment design**
  - Host the UI and lightweight API routes on `Vercel`.
  - Use `Supabase` for Postgres, Auth, and optional Storage for cached filings/transcripts and generated analysis payloads.
  - Do not host the primary LLM on Vercel or Supabase Edge Functions. Those platforms are only for orchestration, persistence, and serving the dashboard.
  - Run qualitative model inference in a separate inference layer: local machine during development, then an optional cheap external VM/container later.
  - All expensive analysis should run asynchronously and persist results so the dashboard reads from cached outputs instead of recomputing on every page load.
- **Core analysis pipeline**
  - Accept a ticker input, resolve the company/CIK, fetch recent SEC filings (`10-K`, `10-Q`, `8-K` earnings items when available), and extract or normalize core metrics: revenue, net income, EPS, gross margin, operating margin, free cash flow, debt, cash, shares outstanding, growth rates.
  - Pull free market and metadata inputs for current price, market cap, sector/industry tags, analyst consensus if available, and historical price performance. Default provider mix: SEC EDGAR for filings, Yahoo Finance or `yfinance` for market data, and a free-tier source such as Finnhub only where needed for profile/peer metadata.
  - Build a peer-discovery module using sector/industry classification first, then refine peers by size and business similarity. Show 5-10 peers and compare growth, margins, valuation multiples, and recent performance.
  - Add a document-analysis layer with a fixed schema: management tone, guidance direction, major risks, capital-allocation signals, and notable changes vs prior period. Numeric values remain sourced from structured extraction only.
- **Model strategy under low-cost hosting**
  - Make the finance engine deterministic: weighted factor scoring, peer comparison, and 3-5 year scenario valuation are the source of the rating and return forecast.
  - Standardize v1 on `Qwen2.5-7B-Instruct` as the default local qualitative model because it is the most realistic fit for low-cost local hardware.
  - Use the 7B model only for qualitative tasks such as filing summaries, earnings-call tone, risk extraction, and dashboard explanations.
  - Keep prompts retrieval-first: chunk filings/transcripts, index them with embeddings, retrieve relevant sections, and send only focused context to the model rather than full documents.
  - Add `FinBERT` for financial sentiment/tone classification and `all-MiniLM-L6-v2` or similar small embedding model for semantic retrieval over filing chunks.
  - Treat the LLM as an assistant to the rating engine, not the rating engine itself.
- **Scoring, forecast, and recommendation**
  - Implement an explainable composite rating with weighted pillars: business quality, growth, profitability, balance-sheet strength, valuation, estimate/revision context, and qualitative management/risk signals.
  - Produce a `LongTermRating` such as `Strong Buy`, `Buy`, `Hold`, `Avoid` from score thresholds, plus a confidence band driven by data completeness and signal agreement.
  - Forecast expected 3-5 year return using `base`, `bull`, and `bear` scenarios over revenue growth, margin path, EPS/FCF path, and terminal valuation multiple.
  - Blend analyst sentiment only as one input. If analyst coverage is sparse under free data limits, fall back to “market-implied + peer-multiple” scenarios and label analyst consensus as unavailable.
- **Dashboard UX**
  - Main flow: enter ticker, submit analysis, show either latest cached result or a processing state, then land on a single-stock dashboard.
  - Dashboard sections: price snapshot, overall rating, expected annualized return range, confidence, thesis summary, key financial metrics, trend charts, filing/earnings summary, peer comparison table, valuation/scenario model, and portfolio-fit conclusion for long-term investors.
  - Include explicit explanations for every score component and a “why this rating” panel so the result is auditable.
- **Public interfaces**
  - `POST /analyze/{ticker}`: enqueue or refresh a full analysis job.
  - `GET /analysis/{ticker}`: return latest normalized analysis payload and job freshness metadata.
  - `GET /peers/{ticker}`: return peer list and comparison metrics.
  - Core response types should include `CompanySnapshot`, `FinancialSeries`, `PeerComparison`, `DocumentSummary`, `ScoreBreakdown`, `ForecastScenario`, `InvestmentVerdict`, and `AnalysisJobStatus`.

## Test Plan
- Ticker resolution works for common US equities and rejects invalid/delisted symbols cleanly.
- Filing ingestion correctly populates revenue, net income, EPS, and cash/debt fields for at least large-cap and mid-cap examples.
- Peer selection returns sensible same-industry companies and avoids obviously unrelated firms.
- Score output is stable and explainable when some external fields are missing.
- Forecast scenarios produce bounded, non-nonsensical outputs and annualized return math is correct.
- Retrieval-plus-summary jobs return focused qualitative output from filing chunks and degrade gracefully if the local model layer is unavailable.
- Cached-analysis flow works end to end: first request queues work, later request returns completed results, stale results can be refreshed.
- Dashboard renders loading, queued, success, stale-cache, and no-data states clearly on free-tier hosting.

## Assumptions And Defaults
- v1 is for internal use, so compliance language can be lighter, but the UI should still state this is research support and not personalized financial advice.
- The project should optimize for free data sources first; missing analyst-consensus coverage is acceptable if the app labels it transparently.
- `Vercel + Supabase` are used for app hosting and persistence only, not for hosting the main LLM.
- `Qwen2.5-7B-Instruct` is the default local model for v1 because it balances capability with feasible local memory requirements.
- The investment rating is produced by deterministic scoring plus scenario analysis; open/local models only support qualitative interpretation and explanation.
- Default stack choice is `Next.js + FastAPI + Supabase Postgres`, with local inference during development and an optional separate inference service later.
- v1 prioritizes one excellent single-stock page; a market-wide screener is deferred until the core analysis schema and scoring engine are stable.
