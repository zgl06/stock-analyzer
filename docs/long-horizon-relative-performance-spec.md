# Long-Horizon Relative Performance: Product Goals and Build Plan

This document captures what the stock research product should do around **comparing companies**, **index and sector outperformance**, and **how to train and deploy models** without mixing roles (numeric pipeline vs LLM). Use it as the single place for **intent**, **data contracts**, **phased plan**, and **locked product decisions**.

It aligns with the existing v1 direction in `plan.md` and `mvp-plan.md`: **FastAPI** for ingestion and scoring, **deterministic** ratings and 3-5y scenarios, **Qwen2.5-7B-Instruct** (and RAG) for **text only**, and optional **Supabase** for persistence. This spec **adds** a research track for **learned** relative performance vs benchmarks; it does not replace the explainable rules engine unless you later decide to after validation.

---

## Decisions (locked)


| #   | Topic                               | Choice                                                                                                                                                                                                                                                                         |
| --- | ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | Geography                           | **US common stocks** only.                                                                                                                                                                                                                                                     |
| 2   | Universe                            | **Everything** with **enough history and liquidity** (exact thresholds: **TBD** when you operationalize the ETL; not limited to a fixed list like the S&P 500 at the start).                                                                                                   |
| 3   | Liquidity / price floor             | **No hard floor yet**; add later if data quality or microcap noise requires it.                                                                                                                                                                                                |
| 4   | Primary supervised label horizon    | **5 years** (`H = 5y`).                                                                                                                                                                                                                                                        |
| 5   | Broad (market) benchmark            | **SPY** (total return aligned with the stock and sector series).                                                                                                                                                                                                               |
| 6   | Sector structure                    | **One ETF per GICS sector** (11 sector buckets). Implement a **fixed GICS sector → sector ETF** table in code.                                                                                                                                                                 |
| 7   | Short ETF history                   | Use the **parent** sector (or parent benchmark) when a sub-sector or niche ETF is missing or the series is too short, so training windows stay consistent where possible.                                                                                                      |
| 8   | Product placement                   | **Separate** “model view” in the **UI and API** first; **merge or blend** with `LongTermRating` only **after** validation (later change, not the initial ship).                                                                                                                |
| 9   | Primary backtest / eval metric (v1) | **Hit rate of the top tercile** (do names the model scores in the top third **actually** end up in the top third of realized **forward** excess return vs the relevant benchmark, out of sample in time).                                                                      |
| 10  | Data spend (v1)                     | **Free only** (e.g. SEC, **yfinance** and similar); no required paid PIT fundamental or analyst feed for the first build. Quality limits apply; revisit if leakage or coverage is unacceptable.                                                                                |
| 11  | M&A / delisting in **labels**       | **Map to acquirer return** when a merger closes (label path follows the **economic** outcome the shareholder gets, per your mapping rules; document the corporate-action chain in the label pipeline).                                                                         |
| 12  | Compute                             | **Train and ETL on local** hardware first. **Cloud** only if **free** tier is available and acceptable. **Hard VRAM cap: 8 GB** (favor **GBDT/CPU** for tabular v1, **small batches** and **4-bit** if you add neural steps, or outsource heavy jobs to free cloud if needed). |


**Still TBD in implementation (not the ticker table):** define “enough history” and “enough liquidity” for the US common-stock universe; **parent** fallback for **very short** sector ETF history (per locked decision) when a new sector or reclassification limits overlap with your 5y windows.

---

## GICS sector → benchmark ETF (SPDR Select Sector, locked)

Use **SPY** for **broad** excess return. For **sector** excess return, use **one ETF per GICS sector** from the **SPDR Select Sector** family: liquid, tracks **S&P 500 components** in that sector, typical expense about **0.08 to 0.09%**.


| GICS sector            | ETF      | Name                                      |
| ---------------------- | -------- | ----------------------------------------- |
| Energy                 | **XLE**  | Energy Select Sector SPDR                 |
| Materials              | **XLB**  | Materials Select Sector SPDR              |
| Industrials            | **XLI**  | Industrial Select Sector SPDR             |
| Consumer Discretionary | **XLY**  | Consumer Discretionary Select Sector SPDR |
| Consumer Staples       | **XLP**  | Consumer Staples Select Sector SPDR       |
| Health Care            | **XLV**  | Health Care Select Sector SPDR            |
| Financials             | **XLF**  | Financial Select Sector SPDR              |
| Information Technology | **XLK**  | Technology Select Sector SPDR             |
| Communication Services | **XLC**  | Communication Services Select Sector SPDR |
| Utilities              | **XLU**  | Utilities Select Sector SPDR              |
| Real Estate            | **XLRE** | Real Estate Select Sector SPDR            |


The same mapping is stored in code as `backend/gics_sector_etfs.yaml` for ETL, labels, and the future ML panel. When a name’s GICS code maps to a sector, use that row’s ETF for `R_sector` in the 5y label. **XLC** and **XLRE** have **shorter** total-return history than the oldest sector funds; for early **as_of** rows where a series is **missing** or too short, apply the **parent** or proxy rule (locked) in the label pipeline, for example a broader **parent** sector or **SPY** until the sector ETF is available, and document the rule in ETL so backtests are reproducible.

---

## 1. What you want (summary)

1. **Identify names that tend to outperform a broad market index** over a long investment horizon, using **data from filings**, **stock prices**, and **analysts / predictions** (and peer-relative context, not a whole 10-K in one prompt for the **numeric** head).
2. **Compare each name to sector peers** and judge **outperformance vs a GICS sector benchmark** (one ETF per 11 GICS sectors, locked) as well, over the same **5y** forward-looking framing for the ML head.
3. **Horizons:** you care about the **very long** story (e.g. 25-30 years) for **narrative and education**, but **supervised** learning should **not** depend on a single 30-year forward return label (sparse, one path, hard to calibrate). Training and the **primary** product score should use **shorter, repeatable** horizons (e.g. 3-10 years, with **5 years** as the recommended first label) and, if needed, **stability of signals** across rolling windows to support “long-horizon compounder” language without faking a point forecast to 2055.
4. **LLM (Qwen + RAG):** for **qualitative** output in a stable schema (summaries, risks, tone, how to say “we do not know”), **grounded in retrieved filing chunks**, **house style** via SFT if you do it. **Not** the source of revenue, EPS, verdict percentiles, or a memorized “pick stocks” from opinions alone.
5. **Learned relative performance:** a **separate** **tabular** model (or stack) on **point-in-time features** and **supervised labels** (excess return vs index, excess return vs sector), **not** the same dataset as RAG+summary SFT unless you add multimodal or embedding features on purpose.

---

## 2. Core definitions

### 2.1 Excess return vs benchmark

For a fixed horizon **H** (e.g. 5 years) and a fixed **as-of** date (when you lock features):

- **Total return** of the stock over **H** (dividend-adjusted, one currency).
- **Total return** of the **benchmark** (index ETF or sector ETF) over the **same** calendar (or same trading-day) window.
- **Excess return** = stock return minus benchmark return (or one agreed variant: log excess, etc.). Use **one** convention in all training and backtests.

You will have **two** such notions per name:

- **Excess vs broad index:** **SPY** (locked).
- **Excess vs sector:** **One ETF per GICS sector** (11 sectors), with **parent** fallback when a dedicated sector series is too short; see the locked table above.

### 2.2 “Compare financials between companies”

This is **not** “feed two 10-Ks to the LLM and ask which is better.” In the **numeric / ML** path, comparison is **engineered features**:

- Ratios and growth from **mapped, restatement-aware** financial periods.
- **Peer- and sector-relative** metrics: z-scores, percentiles within sector and size bucket, rank among a peer set.
- **Point-in-time (PIT)**: at each `as_of`, only data **available by that date** (plus an optional **filing lag** if you simulate real portfolio formation).

### 2.3 Roles split (no confusion)


| Role                            | Owns                                                                                                                                                             |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Ingestion + Python pipeline** | Fundamentals, peer tables, scenario math, your existing `LongTermRating` / forecast scaffolding.                                                                 |
| **ML model (this spec)**        | Learned **relative** performance vs index and vs sector, from PIT **tabular** features and **historical** labels.                                                |
| **LLM + RAG**                   | Filing-grounded **text** and structured **qualitative** fields; can **narrate** model outputs and risks; must not **invent** the headline excess-return numbers. |


---

## 3. What to train, and what not to train

### 3.1 LLM: supervised finetune (optional)

- **Intent:** SFT (LoRA on full Instruct weights) so the model matches **house tone** and a **locked schema** (e.g. `DocumentSummary`-like).
- **Data shape:** (retrieved chunk(s) + task instruction) **→** target summary / structured text.
- **Inference:** RAG at runtime; **do not** put a whole 10-K in the prompt.
- **Serving:** train in PyTorch / Hugging Face; for Ollama, **merge** and convert to **GGUF** after training, not train inside Ollama.
- **Not:** replacing the **numeric** pipeline, or training only on personal opinions without filing grounding.

### 3.2 Relative performance: tabular ML (this track)

- **Intent:** From **PIT** rows (filings-derived metrics, prices, analyst snapshots), **predict** or **rank** **future** excess return vs **index** and/or **sector** (or deciles, or P(outperform)).
- **Data shape:** One row per `(security_id, as_of)` with **feature columns** and **labels** computed only with information **after** the horizon (for training), with **no leakage** from the future into features.
- **Labels:** For history, **realized** excess return over **H**; for the product, communicate **uncertainty** (deciles, bands, hit rates) rather than a single 30y point number.

You **do not** need the LLM to “predict 30y returns” if this tabular model + your rules engine cover **relative** standing and the LLM covers **explanation and risks**.

---

## 4. Dataset outlines

### 4.1 Tabular training set (index + sector)

**Grain:** `(id, as_of)` with stable id over ticker changes (FIGI/CIK where possible).

**Feature families (PIT only):**

- **Fundamentals:** growth, margins, cash generation, leverage, reinvestment, stability; **sector-relative** and **peer-relative** columns.
- **Market:** size, long-horizon co-movement with index and sector (define carefully to avoid **label** leakage; often **lag** price features).
- **Analysts:** consensus level, **revisions**, dispersion, as-of the snapshot used for the row.
- **Optional:** text embeddings from a fixed window of filings, if you add a multimodal path later.

**Labels (for training rows in the past):**

- `R_stock_H`, `R_index_H`, `R_sector_H` over the **same** window; `excess_index = R_stock - R_index`, `excess_sector = R_stock - R_sector` (or your single convention).
- Store **which** index and sector series were used (IDs and date alignment rules).

**Splits:** **Time-based** (train / val / test by calendar). **Do not** shuffle random rows across years.

### 4.2 LLM SFT set (separate)

- `context` = RAG chunk(s) + optional metadata; `target` = your qualitative schema; **no** made-up financial numbers unless you inject them in the **input** as facts.

---

## 5. Honest scope for “25-30 years”

- A **30-year forward** return is **one realized path**; you get **few** non-overlapping long windows; labels are **noisy** and **regime-dependent**.
- **Product (locked):** use **5y** as the **scored** ML horizon; use **25-30y** only for **historical** charts, education, or “names that repeatedly showed up in top terciles” **narrative**, with clear **disclaimers**.
- **Research:** you may **stack** multiple rolling 5y outcomes in evaluation to see **persistence** of deciles; that **supports** “long-term outperformer” language without claiming a single calibrated 2048 return.

---

## 6. Phased build plan


| Phase | Name                | What                                                                                                                                                                                                                                                                                                                             |
| ----- | ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **0** | Scope and contracts | **Locked:** 5y, SPY, SPDR sector tickers in `backend/gics_sector_etfs.yaml`, parent fallbacks, top-tercile hit rate, separate UI first, free data, M&A to acquirer, 8 GB VRAM. **Still to implement in Phase 0:** thresholds for “enough” history/liquidity; code that loads YAML and maps vendor GICS codes to the 11 row keys. |
| **1** | PIT data foundation | Security master, total-return series (stock, index, sector), fundamentals with **filing/period dates**, analyst snapshots with **as-of** joins.                                                                                                                                                                                  |
| **2** | Label table         | For each `as_of` in the training grid, compute realized **excess_index** and **excess_sector** for **5y**; **M&A: map to acquirer** return; document the chain.                                                                                                                                                                  |
| **3** | Feature engineering | Peer- and sector-relative features; optional analyst and price blocks; data dictionary.                                                                                                                                                                                                                                          |
| **4** | Model v1            | Start with **GBDT** (e.g. LightGBM) on **CPU** if it fits; fine for 8 GB systems. For `excess_index` and for `excess_sector` (or multi-output); time-based validation; ablations; **primary metric: top-tercile hit rate** (out of sample by time).                                                                              |
| **5** | Product             | **Separate** API and UI block for “vs SPY” and “vs sector ETF” (5y framing); **not** merged into the main long-term rating until a later change; LLM explains **without** fabricating the headline numbers.                                                                                                                      |
| **6** | Governance          | Retrain cadence, walk-forward eval, not-investment-advice copy, and limits on long-horizon claims.                                                                                                                                                                                                                               |


For a **reviewable, step-by-step build** (tabular **A–I**, LLM **L1–L4**, optional SFT **L-OPT**, integration **J**, exit criteria), use **[ml-relative-performance-implementation.md](./ml-relative-performance-implementation.md)**.

---

## 7. Further choices (not locked; optional later)

- **Tighten the universe** with explicit min history and min dollar volume if free data is too noisy or expensive to clean.
- **Paid PIT** fundamentals or **point-in-time** analyst if free joins prove leaky or too sparse.
- **Merge** the ML view into the main long-term rating after backtests (per locked decision: **only after** you are ready).
- **GICS → ETF** mapping: fixed in `backend/gics_sector_etfs.yaml` (SPDR list); validate total-return **overlap** with SPY windows and test **XLC** / **XLRE** start dates in the label ETL.

Decisions that were open are now in **Decisions (locked)** at the top of this file.

---

## 8. Relationship to the existing app

- **Ingestion and `AnalysisResponse`:** Reuse and extend; add fields when you are ready (e.g. `ml_forward_view: { vs_index, vs_sector, horizon_years, confidence, as_of }`).
- **Ranking (`ranking.py`, peer percentiles):** Complements the ML block; both can appear on the same page: **rules + peers** and **model-implied** relative performance vs **broad and sector** benchmarks.
- **LLM + RAG:** Unchanged in role: **text** and **explanations**; optional SFT is **orthogonal** to the tabular ML dataset.

---

## 9. One-line reminder

**Fine-tune Qwen for filing-grounded qualitative output in a fixed schema; build a PIT tabular dataset with excess vs SPY and excess vs a GICS sector ETF over 5y; train a separate model and ship it in a separate UI first; top-tercile hit rate is the v1 backtest target; use RAG at inference for text; 25-30y remains narrative, not a supervised target.**