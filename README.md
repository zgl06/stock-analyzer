# stock-analyzer

Full-stack app for **equity research**: ingest public company and market data, run a **deterministic analysis pipeline** (scores, multi-year scenarios, peers, verdict), add **LightGBM relative performance** vs broad and sector benchmarks, optional **SEC filing RAG** with **pgvector**, and optional **LLM qualitative summaries** (Ollama). A **Next.js** dashboard talks to a **FastAPI** backend; **Supabase** stores analysis inputs, filing chunks, and cached summaries.

**Disclaimer:** Outputs are for research and education only, not investment advice.

---

## What it does

| Layer | What you get |
|--------|----------------|
| **Ingestion** | Resolve tickers via SEC, pull filings metadata, fetch **yfinance** prices and profiles, normalize into `AnalysisInput`, persist to Supabase. Optional refresh merges a fresh market snapshot on read. |
| **Core analysis** | Composite **score**, **bear / base / bull** 5y scenario forecasts, **dynamic peers**, **ranking context** (where the name sits vs peers and a liquid cohort), **verdict** and confidence band from scenario returns. |
| **Relative models (5Y)** | Two **LightGBM** regressors (vs **SPY** and vs a **sector ETF** mapped from GICS-style sector strings) produce raw scores and tercile-style bands when model files and feature rows are available. |
| **L1 RAG** | Chunk SEC HTML filings, embed with **sentence-transformers**, store vectors in Supabase, retrieve by semantic similarity (`match_filing_chunks`). |
| **L3 qualitative** | When enabled, retrieve chunks, call **Ollama** with JSON-shaped prompts, validate **DocumentSummary**, cache in `document_summaries`. Auto-index can run if chunk count is low. |

---

## Repository layout

```
backend/                 FastAPI app, analysis engine, services, tests
  app/main.py            ASGI entry
  app/api/routes.py      HTTP API
  app/analysis/          Forecasts, scoring, ranking, dataset and training helpers
  app/services/          SEC, market data, normalize, storage, RAG, qualitative, relative model
  migrations/            SQL for filing_chunks + document_summaries (run after base schema)
  scripts/               Offline smoke, dataset build, train / promote relative models
  supabase/schema.sql    Base tables (companies, analysis payloads, etc.)
  tests/                 Pytest suite
frontend/                Next.js App Router UI (ticker analysis page, cards)
docs/                    Deeper notes (retrain, features, LLM ops, workflow)
```

Generated training outputs and local model binaries live under `backend/outputs/` (gitignored). Point `RELATIVE_MODEL_*` env vars at your copies or leave defaults if you mirror that layout.

---

## Prerequisites

- **Python** 3.11+ (project venv recommended)
- **Node.js** 20+ for the frontend
- **Supabase** project (URL + service role key) for persistence and vector search
- Optional: **Ollama** for qualitative summaries (`ollama serve`, pull a model such as `qwen2.5:7b`)
- Optional: **GPU** helps sentence-transformers and Ollama; CPU works for smaller smoke runs

---

## Configuration

1. Copy `backend/.env.example` to `backend/.env` (and optionally a repo-root `.env` for shared keys).
2. Set at least **`SUPABASE_URL`** and **`SUPABASE_SERVICE_ROLE_KEY`** for live ingestion and `GET /analysis/{ticker}`.
3. Set **`SEC_USER_AGENT`** to a string that identifies you to SEC (see SEC fair access policy).
4. For relative models, set **`RELATIVE_MODEL_*`** paths to your LightGBm model text plus `feature_columns` JSON and optional calibration CSV (see `docs/RETRAIN.md`).
5. For RAG and embeddings, install deps; first chunk indexing downloads the embedding model.
6. For qualitative summaries: **`OLLAMA_BASE_URL`** (for example `http://127.0.0.1:11434`), **`OLLAMA_MODEL`**, and **`ENABLE_QUALITATIVE_SUMMARY=true`**.

Full keys and defaults are documented in `backend/.env.example` and `backend/app/config.py`.

---

## Database setup (Supabase)

1. Run **`backend/supabase/schema.sql`** in the Supabase SQL editor (creates core tables used by ingestion and reads).
2. Run migrations **in order** (see `backend/migrations/README.md`):
   - `001_filing_chunks.sql` … `filing_chunks` + **`match_filing_chunks`** RPC
   - `002_document_summaries.sql` … cache table for qualitative JSON

Re-run is safe where files use `IF NOT EXISTS` style guards.

---

## Backend

From the **repository root** (so `backend` is importable as a package):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
copy backend\.env.example backend\.env
# edit backend\.env
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

API docs: `http://127.0.0.1:8000/docs`

### Main HTTP endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness and Supabase connectivity |
| POST | `/analyze/{ticker}` | Run ingestion and persist latest `AnalysisInput` |
| GET | `/analysis-input/{ticker}` | Fetch stored `AnalysisInput` JSON |
| GET | `/analysis/{ticker}` | Full **`AnalysisResponse`** (score, forecast, peers, ranking, verdict, optional `document_summary`, optional `relative_performance`) |
| GET | `/analysis/{ticker}?refresh=true` | Force full re-ingestion before analysis |
| GET | `/analysis/{ticker}/relative-model` | **RelativePerformanceView** only |
| GET | `/peers/{ticker}` | Peer set for the ticker |
| GET | `/analysis/{ticker}/dashboard` | Legacy HTML dashboard (Jinja) |

---

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. The analysis route expects the API at **`http://127.0.0.1:8000`** (CORS is enabled for localhost dev).

---

## Useful scripts (from repo root, venv on)

| Script | Role |
|--------|------|
| `python -m backend.scripts.smoke_rag TICKER` | Index a couple of filings and smoke-test retrieval (needs Supabase + `001` migration + `sentence-transformers`) |
| `python -m backend.scripts.smoke_qualitative TICKER` | End-to-end qualitative smoke (needs Ollama, Supabase, indexed chunks) |
| `python -m backend.scripts.smoke_index_and_summarize ...` | Index if needed and run summaries for multiple tickers |
| `python -m backend.scripts.build_label_dataset` / `build_feature_dataset` | Offline dataset builds |
| `python -m backend.scripts.train_relative_model` / `promote_relative_model` | Train or promote LightGBM bundles (see `docs/RETRAIN.md`) |
| `python -m backend.scripts.validate_relative_model_env` | Check paths and deps for relative inference |

---

## Tests

```powershell
python -m pytest backend\tests -q
```

Many tests mock external services; a few are gated by environment markers where noted in test files.

---

## Documentation

- **`docs/RETRAIN.md`** … relative model training and promotion
- **`docs/features_v1.md`** … feature column vocabulary
- **`docs/llm_ops.md`** … Ollama and qualitative behavior
- **`docs/stock-analyzer-workflow.md`** … end-to-end flow
- **`backend/migrations/README.md`** … applying SQL migrations

---

## Tech stack (short)

**Backend:** FastAPI, Pydantic, httpx, yfinance, Supabase client, LightGBM, pandas, NumPy, scikit-learn, sentence-transformers, BeautifulSoup, PyYAML  

**Frontend:** Next.js (App Router), React, TypeScript, Tailwind  

**Data:** Supabase Postgres, **pgvector** for retrieval, optional Ollama for local LLM JSON generation

---

## Contributing and license

Issues and PRs welcome. Add or update tests when you change analysis or API contracts. If the repo gains a formal license file, it overrides this sentence; until then treat usage as private to your deployment unless stated otherwise by the maintainers.
