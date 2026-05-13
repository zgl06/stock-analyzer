# Step-by-step implementation: tabular model + LLM

This is the **build order** for [long-horizon-relative-performance-spec.md](./long-horizon-relative-performance-spec.md). It covers **two** kinds of “model”:

1. **Tabular ML (e.g. LightGBM):** point-in-time features in, **5y relative** signal out (vs **SPY** and vs **GICS sector ETF**). This is the **relative performance** track (Phases **A–I**).
2. **LLM (Qwen + RAG):** **text** in a fixed schema, **grounded in retrieved filing chunks**; not the source of your numeric truth. This is the **qualitative** track (Phases **L1–L4**), plus **optional SFT (L-OPT)** and a **product integration** phase **J** that ties both together in the UI.

**Stop after each phase**, run **How to review**, then ask to continue.

---

## How the pieces fit (read this first)


| Piece               | What it does                                                                                                                                                                                                                                | Phases                                     |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| **Tabular ML**      | Learns from **historical** PIT **rows** to rank or predict **excess** vs **SPY** and vs **sector** over your **5y** label.                                                                                                                  | **A–I** (train in **G**, ship in **H**)    |
| **LLM + RAG**       | **Summaries**, tone, risks, thesis, “thin evidence” guardrails, **RAG** from chunks.                                                                                                                                                        | **L1–L4**; **SFT** is **L-OPT** (optional) |
| **Both in the app** | Dashboard shows **numbers** from Python + (when ready) the **saved** tabular model, and **prose** from the **LLM**; optional **J** makes the LLM **explain** the tabular readout using **injected** numbers so it does not **invent** them. | **H** (tabular UI) and **J** (integration) |


**Parallel work:** The **L** phases do **not** require **A** to be done first. You can start **L1** as soon as you have a working analysis flow and filings. The **tabular** Phases **A–F** are **mostly independent** of the **LLM** path until you need a **unified** page (**H + J**).

**Suggested first-time order if one person, one machine:** **A** → **B** → **C** (get labels right), and in **parallel** when ready **L1** → **L2** (RAG + schema). Then **D–E–F** → **G** → **H** for the tabular side; keep **L3–L4** moving alongside **F–G** if possible. **J** is **after** you have at least **L2** (qual working) and **H** (tabular block working).

---

# Track 1: Tabular ML (relative performance vs SPY and sector)

**Conventions:** Phases **A, B, C, … I** for this track only.

## Phase A: Config in code and GICS → sector ETF

**Goal:** The backend **loads** `backend/gics_sector_etfs.yaml` and can answer: “for this GICS **sector** name, which SPDR **ticker** is the 5y sector benchmark?”

**Build:**

- Python module, e.g. `backend/app/analysis/benchmarks.py` (or `services/benchmarks.py`), that:
  - Parses the YAML (use `pathlib` + `pyyaml` or `ruamel.yaml`; add `pyyaml` to backend deps if missing).
  - Exposes: `BROAD_BENCHMARK_TICKER` → `SPY`, `sector_etf_ticker(gics_sector: str) -> str | None` with **fuzzy/alias** match for yfinance sector strings (e.g. `Technology` vs `Information Technology`), `list_sector_etf_names()` for logs.
- Unit tests: every row in the YAML returns a unique ticker; unknown sector returns `None` or a documented default (no silent wrong ETF).

**How to review:**

- Run the test suite for this module; spot-check 2 to 3 sector strings you see on Yahoo (e.g. AAPL, XOM) in a REPL or a tiny `__main__` script.

**Out of scope for A:** No price data, no labels, no API.

---

## Phase B: Total return over a window (stocks, SPY, sector ETF)

**Goal:** **One function** (or small module) that, given `ticker`, `start`, `end`, returns **dividend-adjusted total return** over that window using the **same** rules for stock and ETF, suitable for a **5y** label. Uses **free** data (e.g. yfinance `auto_adjust` or explicit adj close) and documents limitations.

**Build:**

- `returns.py` (or under `benchmarks/`): `total_return_log_or_simple(ticker, start, end) -> float | None` with clear docstring on calendar vs trading days (pick **one** convention, e.g. first trading day on/after `as_of` to `+5y`).
- For **XLC** and **XLRE**, return `None` or a `BenchmarkUnavailable` when history does not cover the full window; **do not** silently substitute yet (parent rule lands in **Phase C** or **D**).
- Unit tests with **cached** or **vcr**-style fixtures if network is flaky, or a tight integration test marked slow/optional.

**How to review:**

- Manually compare 1y total return of SPY from the function to a chart or another source for one date (order of magnitude match).

**Out of scope for B:** No batch over universe, no M&A.

---

## Phase C: 5y excess vs SPY and vs sector (single ticker, many `as_of`)

**Goal:** For a **single** US stock, for a list of `as_of` monthly or quarterly dates, compute **realized** `R_stock - R_SPY` and `R_stock - R_sector_etf` over the **next** 5y (only where history exists). This is the **label** definition in code, still research-only (Parquet/CSV or in-memory, not the full app).

**Build:**

- Resolve company **sector** from current ingestion (e.g. `AnalysisInput` / yfinance) for **ticker**; map to row via Phase A. If sector is missing, skip or log.
- **Parent fallback (minimal):** if sector ETF return is `None` for the window, use **SPY** as the sector leg only when documented (so label is `excess` vs a broad proxy) **or** drop the row, per a single flag in code. **Document** the choice in the module docstring.
- Output: a small table or `pandas` DataFrame: `as_of`, `r_stock_5y`, `r_spy_5y`, `r_sector_5y`, `excess_spy`, `excess_sector`, `sector_etf_used`.

**How to review:**

- Run for 2 to 3 tickers (e.g. large cap in XLK, XLE) and spot-check 1 to 2 `as_of` points against hand calculation with same dates.

**Out of scope for C:** No training set over thousands of names, no M&A to acquirer (delisted names may be missing; document).

---

## Phase D: M&A and delisting policy (label pipeline v1)

**Goal:** When a name **merges** into another, **map to acquirer** return (per spec) for the **5y** path where data allows, or a clear **dropped/invalid** reason. Free data often limits this: implement **best effort** and log gaps.

**Build:**

- Document fields available from yfinance (or SEC) for corporate actions; if insufficient for full acquirer mapping, v1 = **“skip row with reason”** and a **TODO** to wire a better feed later.
- Optional: one known historical merger case in a test as **regression** if you can get clean dates.

**How to review:**

- Read the docstring and one example; agree that the behavior matches your risk tolerance for training labels (biased if too many drops).

**Out of scope for D:** Full CRSP-style survivor bias fix (paid or heavy).

---

## Phase E: Training grid and batch labels (no ML yet)

**Goal:** A **script** or job that enumerates `ticker, as_of` (from a CSV or a rule like “all Fridays 2005–2018”) and writes **label Parquet/CSV** for backtesting. Respects “enough history” once you set **TBD** thresholds (can start loose).

**Build:**

- Config: `min_trading_days_price`, maybe `min_market_cap` when available.
- Idempotent run, resumable logs, and a **row count** + **date coverage** report.

**How to review:**

- Inspect file size, null rates, and distribution of `excess_spy` / `excess_sector` (rough sanity, no need for ML yet).

**Out of scope for E:** Features (fundamentals) not required yet; can be “labels only” for pipeline proof.

---

## Phase F: Point-in-time features (v1, free data)

**Goal:** Join **PIT** fundamentals and analyst snapshots at `as_of` where your pipeline can already provide them, plus simple **lagged** price features. Align with [analysis_output](./stock-analyzer-workflow.md) where possible so you do not duplicate logic forever.

**Build:**

- Feature spec table (name, source, PIT rule) in a short `features_v1.md` in `docs/` or in module docstring.
- Build `(id, as_of) → feature vector` for the same grid as **Phase E** (subset ok for first pass).

**How to review:**

- Correlation and missingness by year; no obvious future columns (e.g. “EPS for fiscal year that ends after `as_of`” without lag).

**Out of scope for F:** Text embeddings, paid PIT vendor.

---

## Phase G: Tabular model v1 (LightGBM) and time-based evaluation

**Goal:** **Train** on an early period, **validate**, **test** on a later one; **primary metric: top-tercile hit rate** on out-of-time test for `excess_spy` (and separately `excess_sector` if you train two models). **8 GB** preference: table fits in RAM; use **CPU** training.

**Build:**

- `notebooks/` or `backend/scripts/` with a pinned `requirements-ml.txt` (lightgbm, pandas, scikit-learn).
- Save: model file(s), `feature_names.json`, `metrics.json` (hit rate, baseline comparisons).
- **Baselines:** “always predict median” or “sector mean” for comparison.

**How to review:**

- Test set hit rate vs baseline; check that metrics are on **out-of-time** data only.

**Out of scope for G:** Production API, front end.

---

## Phase H: Product (separate API + UI for the **tabular** model)

**Goal:** Expose a **separate** “model view” (per spec): e.g. `GET /analysis/{ticker}/relative-model` or a field on the analysis object behind a feature flag, with **5y** framing, `as_of`, and “not investment advice” copy. **No** merge into the main `LongTermRating` until you decide.

**Build:**

- Load **saved** tabular model, same feature builder as F for **current** `as_of` (usually “today” or last close).
- Frontend panel: vs **SPY** / vs **sector** **bucket or score** + data completeness.

**How to review:**

- UI on 2 to 3 tickers; error states when the model or features are missing.

**Out of scope for H:** This phase does **not** add new **LLM** behavior; the LLM is covered in **L1–L4** and the optional tie-in in **J**.

---

## Phase I: Governance and retrain runbook (tabular)

**Goal:** How often to **refresh** labels, **retrain** the **LightGBM** model, and re-run the **hit rate** check; user-facing **disclaimers** and limits on long-horizon claims (see spec section 5).

**Build:** `docs/RETRAIN.md` + retrain script + preflight validation.

**Phase I checklist (tabular):**

- Versioned retrain artifacts (`model.txt`, `feature_names.json`, `metrics.json`, `test_predictions.csv`)
- Gate decision logged and reviewed
- Stable promotion step for chosen release
- Env preflight script confirms artifact paths
- Rollback instructions documented and tested once

**How to review:** You read and adjust cadence to your time budget.

---

# Track 2: LLM + RAG (qualitative)

These phases use **Qwen2.5-7B-Instruct** (or your chosen local model) with **RAG** over **filing chunks**, per `plan.md` and the spec. They do **not** replace the **tabular** model; they **explain** the **world** the filings describe.

## Phase L1: RAG foundation (embeddings, store, retrieve)

**Goal:** **Production-shaped** RAG: chunk SEC text, embed, retrieve **top-k** relevant chunks for a **ticker + task**, with limits (token cap, min score). Same path you will use at **inference** after any optional SFT.

**Build:**

- Embedding model (e.g. `all-MiniLM-L6-v2` or what you already use) and where vectors live (in-memory, SQLite, or Supabase if you use it).
- **Chunking** policy documented (size, overlap, which filing types).
- **Retrieve** function: `(ticker, query or section intent) -> list[chunk]` for downstream prompts.

**How to review:**

- For 1 to 2 tickers, retrieve chunks and confirm they are **on-topic** for a test query (e.g. “revenue risk”).

**Out of scope for L1:** No fine-tune yet. No tabular model.

---

## Phase L2: Qualitative **schema** and prompts (no new numbers from the model)

**Goal:** **Stable** output shape (e.g. `DocumentSummary`: tone, risks, positives, short thesis, guidance flavor). **Prompts** that forbid inventing **EPS**, **revenue**, or **benchmark** numbers unless pasted into the **user** content as **facts**. Graceful **fallback** if the model or RAG is down.

**Build:**

- Pydantic or JSON schema for the qual payload; **validate** model output, retry or strip on failure.
- Unit or integration test: with **fixed** chunks and **fixed** “facts” block, the response contains **no** new numeric **facts** (regex or allowlist of allowed numbers from input only).

**How to review:**

- Run 3 to 5 real tickers; spot-check for hallucinated figures.

**Out of scope for L2:** LoRA SFT (that is **L-OPT**).

---

## L-OPT: Supervised finetune (SFT) for **house style** (optional)

**Goal:** **LoRA** on top of **Qwen2.5-7B-Instruct** (or 4-bit load for VRAM) on **(retrieved context, instruction) →** your qual label in the **same schema** as L2. **RAG** still at **inference**; SFT is **not** a substitute for retrieval.

**Build:**

- Small **dataset** of examples (your labels or **human-edited** model drafts).
- Training script in PyTorch / HF; **save adapters**; optional **merge** and **GGUF** for Ollama per your serving plan.

**How to review:**

- Side-by-side: base RAG vs SFT+ RAG for **adherence to schema** and **tone** on held-out tickers, not on new numeric **accuracy** (the LLM is still not the numbers engine).

**Out of scope for L-OPT:** This does **not** train **LightGBM** or label **excess** returns. Keep datasets **separate**.

---

## Phase L3: LLM in the **app** path (wiring, flags, costs)

**Goal:** The **Analysis** path consistently calls RAG + LLM, persists or caches the **qual** result, and surfaces **errors** and “qualitative **unavailable**” without breaking the page. Aligned with [stock-analyzer-workflow.md](./stock-analyzer-workflow.md) if the code already does most of this, treat L3 as **hardening + contract tests**.

**Build:**

- Clear **API** contract: where `DocumentSummary` (or your name) lives on `GET /analysis/{ticker}`.
- **Feature flag** or config: model name, Ollama URL, max tokens, timeout.
- Optional: **prompt version** in metadata for reproducibility.

**How to review:**

- One full run with LLM on and one with off; dashboard still **loads** and **deterministic** blocks still work.

**Out of scope for L3:** Tabular `relative-model` endpoint (that is **H**).

---

## Phase L4: Qualitative retrain and prompt iteration (not tabular retrain)

**Goal:** A **light** runbook for the **LLM** side: when to **refresh** chunk index, when to **re-run** SFT (if you use L-OPT), A/B of prompt versions, and **safety** checks (PII, “not financial advice” copy).

**Build:** A short **LLM_ops.md** in `docs/` or a subsection in `RETRAIN.md` (tabular vs qual clearly separated).

**How to review:** You are comfortable that **G/I** and **L4** are not confused in ops.

---

# Phase J: **Integration** (product): tabular + LLM on one page, safely

**Goal:** The **analysis** page (or a subsection) shows **both** (1) the **separate** **tabular** panel from **H** and (2) the **qual** block from **L2–L3**. **Optional** but recommended: a **second** LLM call (or a **section** in a single call) with **injected** **structured** facts: `excess` **percentiles** or **terciles** from the **saved** model, current **verdict** from your **rules engine**, and **excerpted** RAG text. The prompt says: **do not invent or change these numbers; explain them in the context of the filings.**

**Build:**

- Template fields: `tabular_model: { ... }` from **H**; `facts: { ... }` from your pipeline; `chunks: [ ... ]` from **L1**.
- Frontend: layout order and mobile behavior; no duplicate **headline** **numbers** in two styles unless intentional.

**How to review:**

- 2 to 3 tickers: check that the **narrative** does not **contradict** the **injected** **facts**; if it does, tighten the prompt (still **J**, not a new model).

**Out of scope for J:** Merging the **tabular** **score** into the **main** **verdict** **badge**; that is a **product** **decision** **after** you **trust** **G**.

---

## Pause-point summary (all tracks)


| Phase     | Track     | You should feel confident that                                                                              |
| --------- | --------- | ----------------------------------------------------------------------------------------------------------- |
| **A–C**   | Tabular   | GICS, returns, and **5y** **excess** **labels** are right.                                                  |
| **D–E**   | Tabular   | M&A and **batch** **labels** are acceptable for v1.                                                         |
| **F**     | Tabular   | **PIT** **features** **join** without look-ahead.                                                           |
| **G**     | Tabular   | **LightGBM** **beats** **baselines** out-of-time (or you know why not).                                     |
| **H, I**  | Tabular   | **API/UI** and **retrain** **runbook** for the **relative** model.                                          |
| **L1–L2** | LLM       | **RAG** **retrieval** and **qual** **schema** are solid; **no** **invented** **fundamentals** in **prose**. |
| **L-OPT** | LLM (opt) | **SFT** **improves** **tone** **/ schema**, **RAG** **unchanged** at run time.                              |
| **L3–L4** | LLM       | **App** **wiring** and **ops** for **qual** are clear.                                                      |
| **J**     | Both      | **One** page **shows** **tabular** + **LLM** **without** the **LLM** **replacing** **numbers**.             |


**When you are ready to implement:** say **“implement Phase A”**, **“implement L1”**, or **“implement J”**, and work **stays** in that **phase** until you **say** otherwise.

---

## Default implementation order (single builder)

1. **A** → **B** → **C** (tabular **labels** in **code**)
2. **L1** → **L2** in **parallel** with **A–C** or **immediately** after (LLM path)
3. **D** → **E** → **F** → **G** (tabular **full** path to **model**)
4. **H** (tabular **UI**)
5. **L3** (LLM **wiring** if not already **done** to your **standard**)
6. **J** (optional **unified** **narrative**)
7. **I** and **L4** (runbooks)
8. **L-OPT** any time after **L2** when you have **SFT** **data**

This order can **slide** (e.g. **H** before **L3** is fine; **G** should **come** after **E–F**).