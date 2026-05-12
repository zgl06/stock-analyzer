# LLM Operations

Operational notes for the LLM + RAG track (Track 2).

---

## L1 — RAG foundation

### Chunking policy

- **Filing types:** 10-K, 10-Q, 8-K (same filter as the tabular pipeline).
- **Chunk size:** ~3 000 chars (~800 tokens at 3.75 chars/token). Breaks are aligned to the nearest sentence boundary within the last 20% of the window to avoid mid-sentence cuts.
- **Overlap:** 200 chars between consecutive chunks to preserve context across boundaries.
- **Pre-processing:** HTML is stripped with BeautifulSoup; `<script>`, `<style>`, `<nav>`, `<header>`, `<footer>` subtrees are removed; probable table-of-contents `<div>` blocks are dropped heuristically (>60% of lines end with a page number pattern).

### Embedding model

| Property | Value |
|---|---|
| Model | `sentence-transformers/all-MiniLM-L6-v2` |
| Dimensions | 384 |
| Normalisation | L2 (cosine similarity via dot product) |
| Runtime | CPU-only; loaded lazily on first use, cached at module level |
| Override | Set `EMBEDDING_MODEL_NAME` env var |

### Applying the migration

The migration lives at `backend/migrations/001_filing_chunks.sql`.

**Option A — Supabase SQL editor:**
1. Open your project dashboard > SQL Editor > New query.
2. Paste the file contents and click Run.

**Option B — Supabase CLI:**
```bash
supabase db execute --file backend/migrations/001_filing_chunks.sql
```

The migration is idempotent (`CREATE ... IF NOT EXISTS` throughout).

### Backfill

A backfill script that iterates all stored companies and calls `RagService.index_filing` will land in L3. Do not run indexing manually until L3 wires the service into the application.

---

## L2 — Qualitative summary (DocumentSummary)

### Schema

`DocumentSummary` lives in `backend/app/models/document_summary.py` and is re-exported from `backend/app/models/__init__.py`.

| Field | Type | Notes |
|---|---|---|
| `tone` | `Literal["positive","neutral","cautious","negative","mixed"]` | Overall tone inferred from filing text |
| `thesis` | `str` | One paragraph ≤ 600 chars; plain-English bull/bear takeaway grounded in chunks |
| `positives` | `list[str]` | 2–5 bullets, each ≤ 240 chars; positive signals from filings |
| `risks` | `list[str]` | 2–5 bullets, each ≤ 240 chars; risk factors from filings |
| `guidance_flavor` | `Literal["raised","reaffirmed","lowered","withdrawn","none_mentioned"]` | Direction of forward guidance |
| `evidence_quality` | `Literal["strong","moderate","thin"]` | `thin` when retrieval returned <2 useful chunks |
| `disclaimer` | `str` | Immutable legal note; model output is ignored and overwritten |
| `prompt_version` | `str` | Stamped by service, not the model (`qual-v1` currently) |
| `model_name` | `str` | Stamped by service from `Settings.ollama_model` |
| `chunk_ids` | `list[str]` | IDs of the filing chunks fed to the model; stamped by service |

Pydantic field validators enforce the length caps and list-size bounds at construction time.

### Prompt version

Current prompt: `qual-v1` (constant `PROMPT_VERSION` in `backend/app/services/_qual_prompts.py`).

Bump the version when the system prompt or the JSON schema inline changes in a way that would invalidate existing `DocumentSummary` outputs.

### No invented numbers rule

Two layers of enforcement:

1. **Prompt instruction** (`SYSTEM_PROMPT` in `_qual_prompts.py`): The model is explicitly told not to write any revenue figure, EPS value, growth percentage, price target, market-cap estimate, or benchmark return unless that exact number appears verbatim in the `FILING EXCERPTS` or the `FACTS` block.  Violating this instruction means fabricating information.

2. **Post-generation regex strip** (`_strip_invented_numbers` in `qualitative.py`): After the model responds, all numeric tokens matching `\$?\d[\d,]*\.?\d*%?` are checked against an allowlist built from the retrieved chunk texts and the injected `facts` dict.  Any sentence containing a number that is not in the allowlist is replaced with `[number redacted]`.  This is a safety net for cases where the model ignores the prompt instruction.

Trade-off: the regex operates at sentence granularity to preserve readability.  It can over-redact if a number the model derived (rather than invented) does not appear verbatim in the source material.  We accept this false-positive risk because hallucinated financial figures are more harmful than a conservative redaction.

### Thin-evidence behavior

If `RagService.retrieve` returns fewer than 2 chunks, `QualitativeService.summarize` short-circuits without calling Ollama and returns a stub `DocumentSummary` with:

- `evidence_quality = "thin"`
- `thesis = "Insufficient filings retrieved to form a grounded view."`
- Generic placeholder bullets for `positives` and `risks`
- `guidance_flavor = "none_mentioned"`
- `tone = "neutral"`

This ensures the API never returns an empty or error state due to a missing index.

### Running the smoke script

```bash
# From the repo root
python -m backend.scripts.smoke_qualitative AAPL
```

Prereqs: Ollama running (`ollama serve`), model pulled (`ollama pull qwen2.5:7b`), `OLLAMA_BASE_URL` set in `backend/.env`, Supabase configured, and the ticker already indexed via the L1 smoke script.

---

## L3 — Application wiring and persistence

### Feature flag

| Variable | Default | Effect when `true` |
|---|---|---|
| `ENABLE_QUALITATIVE_SUMMARY` | `false` | `GET /analysis/{ticker}` calls `QualitativeService.summarize` and populates `AnalysisResponse.document_summary` |

When the flag is off, `document_summary` is `null` and no Ollama call is made. Flip the flag in `backend/.env`.

### Required environment

When the flag is on, these must also be set:

- `OLLAMA_BASE_URL` (e.g. `http://localhost:11434`)
- `OLLAMA_MODEL` (e.g. `qwen2.5:7b`)
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (for the chunk store and the cache table)

### Persistence and cache

Migration: `backend/migrations/002_document_summaries.sql` creates the `document_summaries` table with a unique index on `(company_id, prompt_version, model_name)` and a `created_at desc` lookup index.

`QualitativeService.summarize(ticker)` now:

1. Resolves `company_id` from the `companies` row.
2. Looks up the most recent row for this `(company_id, prompt_version, model_name)`. If `created_at` is within `QUALITATIVE_TTL_HOURS` (24h), returns the parsed `DocumentSummary` and skips Ollama.
3. Otherwise runs the L2 retrieve → prompt → LLM → validate flow.
4. Upserts the new payload into `document_summaries`.

To bust the cache, either bump `PROMPT_VERSION`, change `OLLAMA_MODEL`, or delete the row in Supabase.

### Graceful degradation

The route catches both `LLMError` and any unexpected exception from `QualitativeService.summarize`. On failure, the response is still HTTP 200 with `document_summary: null`. The page never breaks because Ollama is down or Supabase is unreachable.

### End-to-end smoke test

1. Apply migrations 001 and 002 in Supabase.
2. Index a ticker once via the L1 smoke script (`python -m backend.scripts.smoke_rag AAPL`).
3. Set `ENABLE_QUALITATIVE_SUMMARY=true` in `backend/.env`, start `ollama serve`, and `uvicorn backend.app.main:app --reload`.
4. `curl http://localhost:8000/analysis/AAPL` — first call hits Ollama; second call returns from cache near-instantly.

### Frontend contract

`frontend/src/lib/types.ts` exposes a `DocumentSummary` interface that mirrors the backend schema field-for-field (`tone`, `thesis`, `positives`, `risks`, `guidance_flavor`, `evidence_quality`, `disclaimer`, `prompt_version`, `model_name`, `chunk_ids`). UI rendering for these fields is not yet implemented; the types are ready for whichever component picks them up.

---

## L4 — Qualitative ops runbook

L4 is a process layer, not new code. It defines when to refresh inputs, how to roll a new prompt, and the safety bar the qualitative output must clear before going live.

### When to refresh the chunk index

Re-index a ticker's filings when **any** of the following is true:

- A new 10-K, 10-Q, or qualifying 8-K has been filed since the last index.
- The chunker policy changes (chunk size, overlap, or HTML-stripping rules in `backend/app/services/_filing_text.py`).
- The embedding model changes (`EMBEDDING_MODEL_NAME`). A model swap requires re-embedding **every** stored chunk, not an incremental top-up — vectors from different models are not comparable.

Cadence: once per quarter for steady-state coverage; immediately on any of the breaking changes above. There is no scheduled backfill job yet — re-run the L1 smoke script manually per ticker, or write a small loop over `companies`.

### When to bump `PROMPT_VERSION`

Bump `PROMPT_VERSION` in `backend/app/services/_qual_prompts.py` when **any** of these change:

- The system prompt's rules or output schema.
- The JSON shape the model is asked to produce.
- The set of fields the service stamps onto the response.

Bumping is the cache-invalidation lever: the document_summaries unique key includes `prompt_version`, so a new version forces a fresh Ollama call on the next request and stores the new payload alongside the old one (we do not auto-delete prior versions — useful for A/B comparison).

### A/B testing prompt versions

Lightweight protocol:

1. Branch a prompt change behind a new `PROMPT_VERSION` (e.g. `qual-v2-tighter-thesis`).
2. Run `smoke_qualitative.py` against ~5 tickers covering different sectors and evidence qualities (one thin-evidence ticker, one strong, one mixed-tone).
3. For each ticker, diff the resulting `DocumentSummary` payloads (old vs new) and check:
   - `tone` and `guidance_flavor` agree with the underlying filing facts.
   - `thesis` doesn't contradict the bullets.
   - No fabricated numbers slipped past `_strip_invented_numbers`.
4. Promote by changing `PROMPT_VERSION` on `main`. The next request per ticker repopulates the cache.

We do not yet have an automated eval harness; this is checklist-grade review.

### When to re-run SFT (L-OPT)

L-OPT is optional and currently **not in use**. If/when it lands, re-run SFT when:

- A new prompt version has been live long enough to collect at least ~50 acceptable model outputs to use as positive examples.
- The base model is upgraded (new Ollama model, new size).
- Schema changes invalidate the existing fine-tune dataset.

Run-time RAG behavior must remain unchanged regardless of SFT — fine-tuning only shifts the model's tone/format adherence, not retrieval.

### Safety checks before enabling in production

Treat the qualitative output as user-facing copy. Before flipping `ENABLE_QUALITATIVE_SUMMARY=true` in any shared environment, confirm:

- **Disclaimer present.** `disclaimer` is hard-coded server-side (`_DEFAULT_DISCLAIMER`) and a model_validator overwrites whatever the LLM emits. Verify the canonical string `"Not investment advice. Generated from filings; may be incomplete."` is what the frontend renders.
- **No invented numbers.** Spot-check 3–5 summaries for figures (`$`, `%`, large integers) and confirm each appears in at least one of the cited `chunk_ids` excerpts.
- **No PII leakage.** Filings can include names of officers, addresses, and litigation details. The prompt does not solicit any of this, but spot-check that `positives`/`risks` bullets don't surface personal information that would be inappropriate in a retail-facing UI.
- **Failure path verified.** Stop Ollama, hit `/analysis/{ticker}`, confirm 200 response with `document_summary: null` and the rest of the payload intact.
- **Cache TTL acceptable.** Default 24h. If filings cadence or model output stability changes, revisit `QUALITATIVE_TTL_HOURS`.

### Separation from tabular ops

The tabular relative-performance model has its own runbook in `docs/RETRAIN.md` (Phase I). L4 covers only the LLM/qual layer. Do not conflate:

- Bumping `PROMPT_VERSION` (L4) ≠ retraining the tabular model (I).
- Re-indexing chunks (L4) ≠ rebuilding the feature dataset (F).
- An LLM safety regression does not automatically warrant a tabular-model rollback, and vice versa.
