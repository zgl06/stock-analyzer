# Backend Bootstrap

This backend now includes the first runnable ingestion path for:
- resolving a ticker through SEC EDGAR
- fetching recent filing metadata
- fetching market data through `yfinance`
- normalizing the result into `AnalysisInput`
- persisting it to Supabase

## Files
- `app/main.py`: FastAPI app entrypoint
- `app/api/routes.py`: `GET /health`, `POST /analyze/{ticker}`, `GET /analysis-input/{ticker}`
- `app/services/sec.py`: SEC company resolution and filing metadata fetch
- `app/services/market_data.py`: `yfinance` price/profile/history fetch
- `app/services/normalize.py`: build `AnalysisInput` with first-pass normalized financials
- `app/services/storage.py`: Supabase persistence and reads
- `supabase/schema.sql`: table and index setup
- `.env.example`: required environment variables
- `fixtures/analysis-input-aapl.json`: canonical sample payload

## Setup
1. Create a virtual environment.
2. Install dependencies with `pip install -r backend/requirements.txt`.
3. Copy `backend/.env.example` to `backend/.env` and fill in the values.
4. Run the SQL in `backend/supabase/schema.sql` in Supabase.
5. Start the API with `uvicorn backend.app.main:app --reload`.

## Endpoints
- `GET /health`
- `POST /analyze/{ticker}`
- `GET /analysis-input/{ticker}`

## Notes
- Monetary values are stored in USD.
- Percentage-style metrics are stored as decimals.
- Normalized financials prefer quarterly-derived trailing-twelve-month (`TTM`) output when four recent quarters are available; otherwise the latest annual period is labeled `TTM` as a fallback.
- SEC companyfacts metrics are used as fill-ins when yfinance annual statements omit values such as revenue, margins, cash, debt, or free cash flow.
- Financial periods that have no revenue, net income, or margin signal are skipped instead of being emitted as mostly-empty rows.
- `marketData` stays camelCase in serialized JSON so downstream consumers can build against the agreed handoff shape.
- SEC uses mixed hosts here: ticker mapping on `www.sec.gov`, submissions JSON on `data.sec.gov`, and archive links on `www.sec.gov`.
- Ingestion still returns a usable `AnalysisInput` when Supabase persistence is unavailable, but persistence is skipped and the condition is logged.

## Manual Validation
- Run `python backend/scripts/manual_sec_checks.py` to validate the default Person 1 ticker set: `AAPL` (mega-cap), `JPM` (non-tech), and `PLUG` (thinner data coverage).
- The script checks company resolution, filing availability, market price availability, normalized period generation, and whether persistence succeeded or was skipped because Supabase is not configured.

## Known Data Gaps
- SEC companyfacts coverage is best-effort and may be absent for some issuers.
- yfinance field names and financial statement availability vary by ticker and reporting history.
- Quarterly statements can be incomplete, which forces annual fallback for `TTM`.
- Persistence depends on Supabase configuration and connectivity; when unavailable, ingestion continues without storage.
