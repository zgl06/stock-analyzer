# Concurrent Backend Split Plan

## Summary
This plan splits the MVP backend between two people so they can work concurrently without blocking each other. The split is based on a stable internal contract: Person 1 produces normalized analysis inputs, and Person 2 consumes those inputs to produce scores, forecasts, verdicts, and API responses. The schedule assumes each person contributes `1-2 hours per day`.

## Ownership Split

### Person 1: Data Ingestion And Normalization
- Own ticker-to-company resolution and SEC CIK mapping
- Own SEC EDGAR fetchers for recent `10-K`, `10-Q`, and relevant `8-K` filing metadata
- Own free market-data fetchers for price, market cap, sector/industry, and historical price data
- Own normalization into shared internal shapes:
  - `CompanySnapshot`
  - `NormalizedFinancials`
  - `FilingRecord`
  - `MarketDataSnapshot`
- Own database tables and persistence for raw and normalized data
- Deliver stable fixture payloads first, then real ingestion output

### Person 2: Analysis Engine And Orchestration
- Own analysis job lifecycle: `queued | running | completed | failed`
- Own API endpoints:
  - `POST /analyze/{ticker}`
  - `GET /analysis/{ticker}`
  - `GET /health`
- Own deterministic scoring engine
- Own `bear`, `base`, and `bull` forecast engine
- Own peer-selection logic
- Own qualitative-summary orchestration with local `Qwen2.5-7B-Instruct`
- Own final `InvestmentVerdict` assembly and caching
- Build against fixtures first, then switch to real normalized inputs

## Shared Contract To Lock First
- `CompanySnapshot`
- `NormalizedFinancials`
- `FilingRecord`
- `MarketDataSnapshot`
- `AnalysisInput`
- `ScoreBreakdown`
- `ForecastScenario`
- `PeerComparison`
- `DocumentSummary`
- `InvestmentVerdict`
- `AnalysisJobStatus`

### Required Conventions
- All monetary fields use USD
- Percentages are stored as decimals unless clearly marked for UI formatting
- Historical financials use a consistent basis such as annual plus trailing-twelve-month where available
- Nullable fields are explicitly documented
- Missing analyst data does not fail the analysis flow

## Handoff Boundary
Person 1 owns producing this shape:

```ts
type AnalysisInput = {
  company: CompanySnapshot;
  financials: NormalizedFinancials;
  filings: FilingRecord[];
  marketData: MarketDataSnapshot;
};
```

Person 2 owns everything downstream from `AnalysisInput`.

## Deliverables

### Person 1 Deliverables
- Shared fixture JSON for `AnalysisInput`
- Ticker resolution utility
- SEC filing metadata fetcher
- Market-data fetcher
- Financial normalization module
- Database schema for raw data and normalized outputs
- One working path that produces `AnalysisInput` for a real ticker

### Person 2 Deliverables
- Shared fixture consumer for local development
- Analysis job runner and state transitions
- Scoring engine with fixed weights
- Scenario return engine
- Peer selection module
- Qualitative summary pipeline with retrieval-first flow
- Final response assembler for `GET /analysis/{ticker}`
- API handlers for analyze, analysis fetch, and health check

## Daily Schedule

### Day 1
**Person 1**
- Define initial shapes for `CompanySnapshot`, `NormalizedFinancials`, `FilingRecord`, and `MarketDataSnapshot`
- Create one sample `AnalysisInput` fixture for a known ticker

**Person 2**
- Review and finalize the shared contract with Person 1
- Stub API response types and set up analysis modules to read the fixture

### Day 2
**Person 1**
- Implement ticker resolution and SEC CIK lookup
- Start SEC filing metadata fetcher

**Person 2**
- Implement deterministic scoring engine against fixture input
- Define score weights and output structure

### Day 3
**Person 1**
- Implement market-data fetcher for price, market cap, and sector/industry
- Continue SEC ingestion work

**Person 2**
- Implement `bear`, `base`, and `bull` forecast logic
- Define expected return output format

### Day 4
**Person 1**
- Implement normalization for core financial metrics
- Produce first real `AnalysisInput` output from one ticker

**Person 2**
- Implement peer-selection logic using fixture data
- Build `InvestmentVerdict` assembly from score plus forecast outputs

### Day 5
**Person 1**
- Add database tables and persistence for raw filings and normalized data
- Stabilize field names and nullable behavior

**Person 2**
- Implement analysis job states and caching flow
- Build `POST /analyze/{ticker}` and `GET /health`

### Day 6
**Person 1**
- Connect real ingestion pipeline to produce stored normalized outputs
- Validate output on 2-3 real tickers

**Person 2**
- Implement `GET /analysis/{ticker}` using fixture-backed or stubbed assembled output
- Add graceful handling for incomplete data

### Day 7
**Person 1**
- Fix normalization gaps discovered during integration
- Add basic error handling for unsupported or incomplete tickers

**Person 2**
- Implement qualitative-summary orchestration with chunk retrieval and local model call interface
- Add fallback behavior when model output is unavailable

### Day 8
**Person 1**
- Finalize ingestion and normalized output consistency
- Confirm `AnalysisInput` contract is stable

**Person 2**
- Swap fixture inputs for real normalized input from Person 1
- Complete end-to-end analysis assembly

### Day 9
**Person 1**
- Support integration debugging and cleanup
- Add any missing persistence fields needed by the dashboard

**Person 2**
- Test full job lifecycle and response outputs on 3 real tickers
- Tighten API response consistency and error messages

### Day 10
**Person 1**
- Final validation of ingestion, normalization, and persistence
- Document any known data gaps

**Person 2**
- Final validation of scoring, forecasts, verdicts, and qualitative summary fallback
- Document known limitations and handoff notes for frontend integration

## Success Criteria
- Person 1 can generate a valid `AnalysisInput` for a real ticker and persist it
- Person 2 can turn that input into a completed analysis payload without changing upstream ingestion code
- `POST /analyze/{ticker}` and `GET /analysis/{ticker}` work end to end for at least 3 real tickers
- Missing analyst or qualitative data degrades gracefully instead of breaking the pipeline
- Both people can work each day without waiting on unfinished code from the other person

## Assumptions
- The team agrees on the shared types before implementation begins
- Each person works in mostly separate folders or modules to reduce merge conflicts
- The qualitative model remains optional for a successful MVP backend result
- The daily schedule targets progress, not perfect completion within each session
