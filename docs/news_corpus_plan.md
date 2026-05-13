# Plan: expand qualitative corpus beyond 10-K / 10-Q

The qualitative LLM layer currently only sees 10-K and 10-Q chunks. This plan
broadens its corpus so it can pick up material events (foundry deals, CHIPS
Act funding, executive changes, earnings guidance) that don't appear in
annual / quarterly filings until months later.

## Phase 1 — 8-K indexing (1–2 hours)

**Goal:** include recent 8-K filings in the RAG corpus so material events
(deals, earnings releases, exec changes) are retrievable alongside 10-K /
10-Q content.

### Steps

1. **Verify upstream supports 8-Ks.** Confirm
   `SecService.fetch_recent_filings` already returns 8-Ks (it should —
   `FilingRecord.filing_type` accepts `"8-K"`). If yes, skip; if no, extend
   the EDGAR query.
2. **Decide selection policy.** Take the **most recent 8 8-Ks** per ticker,
   no item-code filtering. Rationale: filtering by 8-K item codes (1.01,
   2.02, 5.02, etc.) sounds rigorous but adds maintenance burden, and
   irrelevant 8-Ks (e.g., admin filings) are harmlessly down-ranked by
   retrieval scoring.
3. **Update `_ensure_indexed_for_qualitative` in
   `backend/app/api/routes.py`.** Change the `targets` list construction:

   ```python
   targets = (
       [f for f in filings if f.filing_type == "10-K"][:1]
       + [f for f in filings if f.filing_type == "10-Q"][:1]
       + [f for f in filings if f.filing_type == "8-K"][:8]
   )
   ```

4. **Add a config knob** (`MAX_8K_PER_TICKER`, default 8) so you can dial
   it without code changes.
5. **Tests:**
   - Unit: add an 8-K fixture (small synthetic one) to
     `backend/tests/fixtures/`. Assert `_ensure_indexed_for_qualitative`
     calls `index_filing` for it.
   - Integration: smoke-run on INTC, verify the auto-index pulls 2026-era
     CHIPS-Act / foundry-deal 8-Ks and that retrieval for `"recent
     strategic developments"` surfaces them.
6. **Update `docs/llm_ops.md`** runbook with the new chunk-budget
   expectations: ~30 chunks per ticker after first index instead of ~15.

### Risks / mitigations

- **Chunk count grows ~2×.** Embedding cost roughly doubles on first
  index. Already negligible for a single ticker; only matters at scale.
- **Some 8-Ks are short routine filings (e.g., CFO changes).** They'll be
  in the corpus but ranked low by retrieval. Acceptable.
- **`guidance_flavor` may finally light up.** 8-K earnings releases (item
  2.02) often quote forward guidance verbatim. Expect a meaningful
  fraction of tickers to start showing `raised` / `reaffirmed` / `lowered`
  instead of universal `none_mentioned`.

### Done when

Smoke test on INTC produces a qualitative summary that mentions a
2026-era development (foundry deal, government investment, etc.), and
`pytest backend` stays green.

---

## Phase 2 — Press-release / IR-feed connector (1–2 days)

**Goal:** widen the corpus beyond SEC filings to include company-issued
press releases for whitelisted tickers, with strict source attribution.

### Architecture decisions to make first

- **Storage model.** Two options:
  - **(a) Reuse `filings` + `filing_chunks` tables** with a new
    `filing_type = "press_release"` value. Pro: no new tables, RAG
    retrieval works as-is. Con: muddies the SEC-filings semantics;
    `accession_number` becomes a synthetic ID.
  - **(b) New `press_releases` table** keyed on
    `(company_id, source_url, published_at)`, with a
    `press_release_chunks` parallel to `filing_chunks`. Pro: clean
    separation. Con: RAG service needs to query both and merge.

  **Recommend (a) for v1**, migrate to (b) later if it gets messy. Half
  the value is being able to retrieve filings and PRs together with the
  existing service.

- **Source discovery.** No central registry. Three tiers:
  - **Tier 1 (manual whitelist):** hardcoded `{ticker → IR RSS URL}` in
    `backend/fixtures/ir_feeds.yaml`. Start with ~25 tickers (FAANG +
    test universe).
  - **Tier 2 (auto-discovery):** parse `https://investor.<domain>/rss`
    patterns. Brittle; opt-in.
  - **Tier 3 (paid):** PR Newswire, Business Wire, GlobeNewswire APIs.
    Skip for now.

  **Recommend Tier 1 only for v1.** Maintenance burden is real but
  signal quality matters more than coverage.

### Steps

1. **Create `backend/fixtures/ir_feeds.yaml`.** Map ticker → RSS feed URL
   for ~25 tickers. Validate each feed manually before adding (parses,
   has dated entries, content is press-release prose not site-nav
   garbage).
2. **Build `IrFeedService`** in `backend/app/services/ir_feed.py`:
   - `fetch_feed(ticker)` → returns feed entries with
     `(url, title, published_at, summary)`. Use `feedparser` library.
   - `fetch_article(url)` → fetches HTML, extracts main content with
     `trafilatura` (fall back to `readability-lxml`). Returns plain text
     + extracted publish date.
   - Respect `If-Modified-Since` / `ETag` headers to avoid re-fetching
     unchanged feeds.
   - Rate limit: 1 request/sec per host, with `httpx.AsyncClient` and a
     small async semaphore.
3. **Schema migration `003_press_releases.sql`** if going with option (b).
   Otherwise skip and add a `source_url` column to `filing_chunks`.
4. **Index pipeline.** New
   `RagService.index_press_release(company_id, article)` method that
   mirrors `index_filing`:
   - Synthesizes an `accession_number` like `pr-{sha1(url)[:12]}`.
   - Stores chunks with `filing_type="press_release"` and the
     `source_url` column.
5. **Wire into auto-index.** In `_ensure_indexed_for_qualitative`, after
   the SEC filings pass:
   - If ticker is in the IR-feed whitelist, call
     `IrFeedService.fetch_feed`, dedupe against already-indexed press
     releases, fetch and index up to N (default 12) newest articles
     published in the last 12 months.
6. **Update qualitative prompt** so the LLM knows press-release chunks
   have a different evidence weight: *"Press-release content is
   company-authored marketing; treat as forward-looking, not factual
   reporting."*
7. **Source attribution in `DocumentSummary`.** Press-release chunk IDs
   already flow through `chunk_ids`, but add a
   `source_urls: list[str] | None` field so the frontend can render
   "Sources" links. Migration on `document_summaries.payload` schema →
   bump `PROMPT_VERSION` to `qual-v3`.
8. **Caching / scheduling.** Per-ticker IR-feed fetches are TTL-cached
   for 6 hours. Consider a daily background job (Phase 3) to pre-warm
   popular tickers.
9. **Tests:**
   - Unit: mocked feed parser returns 5 entries, assert dedupe behavior.
   - Unit: HTML extractor handles 3 hand-saved fixtures (Intel IR page,
     generic Business Wire layout, JS-heavy SPA — if SPA fails, log and
     skip).
   - Integration: with `IR_FEEDS_ENABLED=true`, smoke-run on INTC,
     verify foundry-deal press release surfaces in retrieval.
10. **Feature flag.** `IR_FEEDS_ENABLED` env var, default `false`.
    Phase 2 ships dark; flip on per environment.
11. **Frontend.** Add a "Sources" section under the qualitative summary
    listing distinct `source_urls` as clickable links. Type updates in
    `frontend/src/lib/types.ts`.

### Risks / mitigations

| Risk | Mitigation |
| --- | --- |
| HTML extraction breaks on a redesign | Tests on hand-saved fixtures; log + skip on extraction failure rather than 500 |
| PR is marketing puff, not analysis | Prompt explicitly down-weights it; number-guard still strips fabricated figures |
| Feed-URL maintenance burden | Keep whitelist small. Audit quarterly. Don't expand to "auto-discover all tickers" |
| Recency bias (PRs skew positive) | Document as known limitation; rely on 8-Ks for negative material events (which are *required* to be filed there) |
| Cost / rate-limit on IR servers | 1 req/sec, 6h TTL cache, `If-Modified-Since` headers |
| Source-quality drift | Audit log of every URL indexed; periodic spot-check sample |

### Done when

For at least 5 whitelisted tickers, qualitative summaries cite recent
press releases, the frontend renders a Sources section, and
`pytest backend` stays green.

---

## What to ship now vs. defer

**Phase 1 should ship this week** — small change, big quality lift, no new
dependencies, plays nicely with the existing prompt.

**Phase 2 is real product work.** Do a **spike on Intel only** first (one
hardcoded RSS feed, one ticker, no whitelist file, no schema migration,
all manual) and see whether the *qualitative summary actually changes for
the better* before committing to the full plan. If the LLM ends up
parroting press-release marketing at the user, you've made the product
worse. Spike first, decide whether to invest the rest.

## What NOT to do

- **Open-web news scraping** (Yahoo Finance, SeekingAlpha, news
  aggregators). Source-quality nightmare; pump-and-dump pieces and SEO
  spam will leak into summaries.
- **News-sentiment features in the LightGBM relative model.** Would
  require a labeled dataset of historical news → forward returns.
  Big build, marginal gain. The model is fundamentals-driven by design;
  news belongs in the qualitative layer.
- **Aggressive auto-discovery of IR feed URLs.** Brittle. Stick with a
  hand-curated whitelist.
