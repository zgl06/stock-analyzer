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
- Full XBRL extraction is intentionally deferred; first-pass financial periods are best-effort and nullable.
- `marketData` stays camelCase in serialized JSON so downstream consumers can build against the agreed handoff shape.
- SEC uses mixed hosts here: ticker mapping on `www.sec.gov`, submissions JSON on `data.sec.gov`, and archive links on `www.sec.gov`.
