import Link from "next/link";
import TickerSearch from "@/components/TickerSearch";

const COMPARISON_LEFT = [
  "Suggest tickers from headlines",
  "Spit out raw financial PDFs",
  "Show you a chart and stop there",
  "Hide their formulas in a black box",
  "Tell you to 'do your own research'",
];

const COMPARISON_RIGHT = [
  "Pull SEC filings and market data",
  "Normalize financials into one schema",
  "Score five pillars deterministically",
  "Run bear / base / bull forecasts",
  "Return an explainable verdict with proof",
];

const CAPABILITIES = [
  {
    n: "01",
    title: "Filings ingestion",
    body: "Pulls 10-K / 10-Q / 8-K filings from SEC EDGAR and parses them into a typed AnalysisInput. No screen scraping, no hallucinated numbers.",
  },
  {
    n: "02",
    title: "Normalized financials",
    body: "Revenue, margins, EPS, free cash flow, cash, debt — extracted, GAAP-aligned, and stored in Postgres with reproducible reporting basis.",
  },
  {
    n: "03",
    title: "Five-pillar scoring",
    body: "Profitability, growth, balance sheet, valuation, momentum. Each pillar weighted, bounded, and shipped with a one-line rationale.",
  },
  {
    n: "04",
    title: "Scenario forecast",
    body: "Bear, base, and bull scenarios. Revenue CAGR → terminal margin → terminal multiple → annualized return. Bear ≤ base ≤ bull, by construction.",
  },
  {
    n: "05",
    title: "Peer comparison",
    body: "Comparable companies side-by-side: market cap, growth, gross margin, operating margin, and valuation multiples in one table.",
  },
  {
    n: "06",
    title: "Auditable verdict",
    body: "Every number ties back to a filing, a market snapshot, or a documented formula. Rerun the same input, get the exact same verdict.",
  },
];

const WORKFLOW = [
  {
    n: "01",
    title: "Ingest",
    left: "Most screeners",
    leftBody:
      "Show you a stock card with a price, a P/E, and a one-line news blurb.",
    rightBody:
      "POST /analyze/{ticker} — pulls SEC filings + Yahoo market data, normalizes into a typed AnalysisInput, persists to Postgres.",
  },
  {
    n: "02",
    title: "Score",
    left: "AI chatbots",
    leftBody:
      "Generate a long, confident-sounding paragraph that may or may not match the actual filings.",
    rightBody:
      "Run five deterministic pillar scores against the normalized financials. Same input always yields the same composite.",
  },
  {
    n: "03",
    title: "Forecast",
    left: "Spreadsheet templates",
    leftBody:
      "Hand you a 12-tab DCF and ask you to fill in growth, margin, and discount rate yourself.",
    rightBody:
      "Build bear / base / bull scenarios with bounded inputs and a single explainable expected annualized return.",
  },
  {
    n: "04",
    title: "Verdict",
    left: "Sell-side reports",
    leftBody:
      "Take a week to publish, sit behind a paywall, and get revised three days later.",
    rightBody:
      "Assemble Strong Buy / Buy / Hold / Avoid with confidence, expected return range, and a one-paragraph summary.",
  },
];

export default function Home() {
  return (
    <div>
      {/* HERO */}
      <section className="max-w-6xl mx-auto px-6 pt-16 pb-24 sm:pt-24 sm:pb-32 text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-[color:var(--line-strong)] bg-[color:var(--surface)] text-xs font-mono uppercase tracking-wider text-[color:var(--accent-2)] mb-8">
          <svg
            viewBox="0 0 24 24"
            className="w-3.5 h-3.5"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M12 2v4" />
            <path d="M12 18v4" />
            <path d="m4.93 4.93 2.83 2.83" />
            <path d="m16.24 16.24 2.83 2.83" />
            <path d="M2 12h4" />
            <path d="M18 12h4" />
            <path d="m4.93 19.07 2.83-2.83" />
            <path d="m16.24 7.76 2.83-2.83" />
          </svg>
          Deterministic Equity Analysis
        </div>

        <h1 className="text-4xl sm:text-6xl lg:text-7xl font-semibold tracking-tight leading-[1.05] text-[color:var(--foreground)]">
          AI screeners suggest.
          <br />
          <span className="text-gradient-accent">This engine ships verdicts.</span>
        </h1>

        <p className="mt-6 max-w-2xl mx-auto text-base sm:text-lg text-[color:var(--muted-strong)] leading-relaxed">
          Pull live SEC filings and market data, score five pillars
          deterministically, and assemble a long-term verdict you can audit. No
          guessing. No hidden weights. No vibes-based ratings.
        </p>

        <div id="cta" className="mt-10 max-w-xl mx-auto">
          <TickerSearch />
        </div>

        <div className="mt-4 flex items-center justify-center gap-2 text-xs font-mono text-[color:var(--muted)]">
          <span>Try</span>
          <Link
            href="/analysis/AAPL"
            className="text-[color:var(--accent-2)] hover:text-[color:var(--accent)] underline-offset-4 hover:underline"
          >
            AAPL
          </Link>
          <span>·</span>
          <Link
            href="/analysis/MSFT"
            className="text-[color:var(--accent-2)] hover:text-[color:var(--accent)] underline-offset-4 hover:underline"
          >
            MSFT
          </Link>
          <span>·</span>
          <Link
            href="/analysis/GOOGL"
            className="text-[color:var(--accent-2)] hover:text-[color:var(--accent)] underline-offset-4 hover:underline"
          >
            GOOGL
          </Link>
        </div>

        {/* Comparison cards */}
        <div className="mt-16 grid grid-cols-1 md:grid-cols-2 gap-4 text-left">
          <div className="surface rounded-2xl p-6 sm:p-7">
            <div className="text-xs uppercase tracking-wider text-[color:var(--muted)] font-mono mb-4">
              Stock Screeners
            </div>
            <ul className="space-y-3">
              {COMPARISON_LEFT.map((item) => (
                <li
                  key={item}
                  className="flex items-start gap-3 text-sm text-[color:var(--muted-strong)]"
                >
                  <span className="mt-0.5 grid place-items-center w-4 h-4 rounded-full bg-[color:var(--surface-raised)] border border-[color:var(--line)] text-[color:var(--muted)]">
                    <svg
                      viewBox="0 0 24 24"
                      className="w-2.5 h-2.5"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="3"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M18 6 6 18" />
                      <path d="m6 6 12 12" />
                    </svg>
                  </span>
                  {item}
                </li>
              ))}
            </ul>
          </div>

          <div className="surface-strong rounded-2xl p-6 sm:p-7 glow-accent">
            <div className="text-xs uppercase tracking-wider text-[color:var(--accent-2)] font-mono mb-4">
              Stock Analyzer — Deterministic Engine
            </div>
            <ul className="space-y-3">
              {COMPARISON_RIGHT.map((item) => (
                <li
                  key={item}
                  className="flex items-start gap-3 text-sm text-[color:var(--foreground)]"
                >
                  <span className="mt-0.5 grid place-items-center w-4 h-4 rounded-full bg-[color:var(--accent)]/20 border border-[color:var(--accent)]/40 text-[color:var(--accent)]">
                    <svg
                      viewBox="0 0 24 24"
                      className="w-2.5 h-2.5"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="3.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M20 6 9 17l-5-5" />
                    </svg>
                  </span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="mt-10 max-w-3xl mx-auto rounded-xl border border-dashed border-[color:var(--line-strong)] bg-[color:var(--surface)] px-6 py-5 text-left">
          <div className="text-xs uppercase tracking-wider font-mono text-[color:var(--muted)] mb-1.5">
            What this engine does not do
          </div>
          <p className="text-sm text-[color:var(--muted-strong)] leading-relaxed">
            It does not pick tomorrow&apos;s winner, time the market, or replace
            your judgment. It executes a transparent, repeatable analysis on
            normalized financials and reports honestly when data is missing.
          </p>
        </div>
      </section>

      <div className="divider-fade max-w-6xl mx-auto" />

      {/* CAPABILITIES */}
      <section
        id="capabilities"
        className="max-w-6xl mx-auto px-6 py-24 sm:py-32"
      >
        <div className="max-w-2xl mb-12">
          <div className="text-xs uppercase tracking-wider font-mono text-[color:var(--accent-2)] mb-3">
            From Filings to Verdict
          </div>
          <h2 className="text-3xl sm:text-4xl font-semibold tracking-tight leading-tight">
            Every step is deterministic, bounded, and auditable.
          </h2>
          <p className="mt-4 text-[color:var(--muted-strong)] leading-relaxed">
            A typed pipeline that turns raw SEC filings and market snapshots into
            a long-term verdict — without guessing or silent failures.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-px bg-[color:var(--line)] rounded-2xl overflow-hidden border border-[color:var(--line)]">
          {CAPABILITIES.map((cap) => (
            <div
              key={cap.n}
              className="bg-[color:var(--background)] p-6 sm:p-7 hover:bg-[color:var(--surface)] transition-colors group"
            >
              <div className="text-xs font-mono text-[color:var(--accent)] mb-4">
                {cap.n}
              </div>
              <h3 className="text-lg font-semibold mb-2 text-[color:var(--foreground)] group-hover:text-[color:var(--accent-2)] transition-colors">
                {cap.title}
              </h3>
              <p className="text-sm text-[color:var(--muted-strong)] leading-relaxed">
                {cap.body}
              </p>
            </div>
          ))}
        </div>
      </section>

      <div className="divider-fade max-w-6xl mx-auto" />

      {/* WORKFLOW comparison */}
      <section id="workflow" className="max-w-6xl mx-auto px-6 py-24 sm:py-32">
        <div className="max-w-2xl mb-12">
          <div className="text-xs uppercase tracking-wider font-mono text-[color:var(--accent-2)] mb-3">
            From Headlines to Holdings
          </div>
          <h2 className="text-3xl sm:text-4xl font-semibold tracking-tight leading-tight">
            They give you a chart. This engine ships a verdict.
          </h2>
        </div>

        <div className="space-y-4">
          {WORKFLOW.map((step) => (
            <div
              key={step.n}
              className="surface rounded-2xl p-6 sm:p-7 grid gap-6 lg:grid-cols-[140px_1fr_1fr] lg:items-center"
            >
              <div>
                <div className="text-xs font-mono text-[color:var(--accent)] mb-1">
                  {step.n}
                </div>
                <h3 className="text-xl font-semibold tracking-tight">
                  {step.title}
                </h3>
              </div>
              <div className="rounded-lg bg-[color:var(--surface-raised)] border border-[color:var(--line)] px-4 py-3">
                <div className="text-[11px] uppercase tracking-wider font-mono text-[color:var(--muted)] mb-1">
                  {step.left}
                </div>
                <p className="text-sm text-[color:var(--muted-strong)] leading-relaxed">
                  {step.leftBody}
                </p>
              </div>
              <div className="rounded-lg bg-[color:var(--accent)]/8 border border-[color:var(--accent)]/30 px-4 py-3">
                <div className="text-[11px] uppercase tracking-wider font-mono text-[color:var(--accent-2)] mb-1">
                  Stock Analyzer
                </div>
                <p className="text-sm text-[color:var(--foreground)] leading-relaxed">
                  {step.rightBody}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <div className="divider-fade max-w-6xl mx-auto" />

      {/* EXAMPLES + CLI block */}
      <section id="examples" className="max-w-6xl mx-auto px-6 py-24 sm:py-32">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          <div>
            <div className="text-xs uppercase tracking-wider font-mono text-[color:var(--accent-2)] mb-3">
              Built on real APIs
            </div>
            <h2 className="text-3xl sm:text-4xl font-semibold tracking-tight leading-tight">
              FastAPI on the back. Next.js on the front. Postgres in the middle.
            </h2>
            <p className="mt-4 text-[color:var(--muted-strong)] leading-relaxed">
              The same endpoint that powers this dashboard is the one you can
              call from a notebook, a CRON job, or a trading playbook.
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/analysis/AAPL"
                className="inline-flex items-center gap-2 text-sm font-medium px-4 py-2.5 rounded-full bg-[color:var(--accent)] text-[#04150f] hover:bg-[color:var(--accent-2)] transition-colors shadow-[0_0_28px_-6px_rgba(52,211,153,0.7)]"
              >
                See AAPL example
                <svg
                  viewBox="0 0 24 24"
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M5 12h14" />
                  <path d="m12 5 7 7-7 7" />
                </svg>
              </Link>
              <a
                href="http://127.0.0.1:8000/docs"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 text-sm font-medium px-4 py-2.5 rounded-full border border-[color:var(--line-strong)] bg-[color:var(--surface)] text-[color:var(--foreground)] hover:border-[color:var(--accent)] transition-colors"
              >
                Open API docs
              </a>
            </div>
          </div>

          <div className="surface-strong rounded-2xl overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-[color:var(--line)] text-xs font-mono">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-rose-400/70" />
                <span className="w-2.5 h-2.5 rounded-full bg-amber-400/70" />
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400/70" />
                <span className="ml-3 text-[color:var(--muted)]">
                  stock-analyzer · terminal
                </span>
              </div>
              <span className="text-[color:var(--accent-2)]">live</span>
            </div>
            <div className="p-5 font-mono text-[13px] leading-relaxed space-y-3">
              <div>
                <div className="flex gap-2">
                  <span className="text-[color:var(--accent)]">❯</span>
                  <span className="text-[color:var(--foreground)]">
                    curl -X POST localhost:8000/analyze/MSFT
                  </span>
                </div>
                <div className="text-[color:var(--muted)] pl-5">
                  → ingested filings, persisted normalized financials.
                </div>
              </div>
              <div>
                <div className="flex gap-2">
                  <span className="text-[color:var(--accent)]">❯</span>
                  <span className="text-[color:var(--foreground)]">
                    curl localhost:8000/analysis/MSFT
                  </span>
                </div>
                <div className="text-[color:var(--muted)] pl-5">
                  → composite 0.74 · forecast bear/base/bull · verdict Buy
                </div>
              </div>
              <div>
                <div className="flex gap-2">
                  <span className="text-[color:var(--accent)]">❯</span>
                  <span className="text-[color:var(--foreground)]">
                    open localhost:3000/analysis/MSFT
                  </span>
                </div>
                <div className="text-[color:var(--accent-2)] pl-5">
                  ✓ dashboard rendered with full audit trail.
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
