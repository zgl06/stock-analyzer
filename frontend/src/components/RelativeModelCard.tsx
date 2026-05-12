import type { RelativePerformanceView, RelativeTercileEstimate } from "@/lib/types";

interface RelativeModelCardProps {
  model: RelativePerformanceView | null;
}

function tercileLabel(t: number | null): string {
  if (t === 3) return "Top Tercile";
  if (t === 2) return "Middle Tercile";
  if (t === 1) return "Bottom Tercile";
  return "Unavailable";
}

function badgeClass(t: number | null): string {
  if (t === 3) return "border-emerald-400/40 bg-emerald-400/10 text-emerald-300";
  if (t === 2) return "border-amber-400/40 bg-amber-400/10 text-amber-300";
  if (t === 1) return "border-rose-400/40 bg-rose-400/10 text-rose-300";
  return "border-[color:var(--line)] bg-[color:var(--panel-subtle)] text-[color:var(--muted)]";
}

function EstimateRow({
  title,
  estimate,
}: {
  title: string;
  estimate: RelativeTercileEstimate;
}) {
  return (
    <div className="rounded-xl border border-[color:var(--line)] bg-[color:var(--panel-subtle)] p-4 space-y-2">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs uppercase tracking-[0.18em] font-mono text-[color:var(--muted)]">
          {title}
        </p>
        <span className="text-xs font-mono text-[color:var(--muted)]">
          {estimate.benchmark_ticker}
        </span>
      </div>
      <span
        className={`inline-flex items-center px-2 py-1 rounded-full border text-[11px] uppercase tracking-[0.14em] font-mono ${badgeClass(
          estimate.tercile,
        )}`}
      >
        {tercileLabel(estimate.tercile)}
      </span>
      <p className="text-sm text-[color:var(--fg)]">
        Score:{" "}
        <span className="font-mono text-[color:var(--accent-2)]">
          {estimate.score == null ? "n/a" : estimate.score.toFixed(3)}
        </span>
      </p>
      {estimate.detail && (
        <p className="text-xs text-[color:var(--muted)] leading-relaxed">{estimate.detail}</p>
      )}
    </div>
  );
}

export default function RelativeModelCard({ model }: RelativeModelCardProps) {
  if (!model) {
    return (
      <section className="rounded-2xl border border-[color:var(--line)] bg-[color:var(--panel)] p-5">
        <p className="text-xs uppercase tracking-[0.18em] font-mono text-[color:var(--muted)]">
          Relative Model (5Y)
        </p>
        <p className="mt-2 text-sm text-[color:var(--muted)]">Model view unavailable.</p>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-[color:var(--line)] bg-[color:var(--panel)] p-5 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs uppercase tracking-[0.18em] font-mono text-[color:var(--muted)]">
          Relative Model ({model.horizon_years}Y)
        </p>
        <p className="text-xs font-mono text-[color:var(--muted)]">as-of {model.as_of}</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <EstimateRow title="vs SPY" estimate={model.vs_spy} />
        <EstimateRow
          title={`vs Sector${model.sector_etf ? ` (${model.sector_etf})` : ""}`}
          estimate={model.vs_sector}
        />
      </div>
      <p className="text-xs text-[color:var(--muted)] leading-relaxed">{model.disclaimer}</p>
    </section>
  );
}

