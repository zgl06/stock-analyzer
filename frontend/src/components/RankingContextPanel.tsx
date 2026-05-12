import Card from "./Card";
import type { RankingContext as RankingContextType } from "@/lib/types";

function formatPctile(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "N/A";
  }
  return Math.round(value).toString();
}

function Stat({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="rounded-xl border border-[color:var(--line)] bg-[color:var(--surface-2)]/40 px-4 py-3">
      <p className="text-[10px] uppercase tracking-[0.16em] font-mono text-[color:var(--muted)]">
        {label}
      </p>
      <p className="text-lg font-semibold tabular-nums text-[color:var(--foreground)] mt-1">
        {value}
      </p>
      {sub && (
        <p className="text-[11px] text-[color:var(--muted)] mt-0.5">{sub}</p>
      )}
    </div>
  );
}

export default function RankingContextPanel({
  context,
  peerCount,
}: {
  context: RankingContextType;
  peerCount: number;
}) {
  const ap = context.among_peers;

  return (
    <Card
      eyebrow="Rank context"
      title="Peer, industry, and market standing"
      subtitle="Percentile vs each cohort: higher = stronger on the blended growth, margin, and value proxy (not a return forecast)."
    >
      <div className="space-y-5">
        <div>
          <p className="text-xs text-[color:var(--muted)] mb-3">
            Among peer set ({peerCount} names vs you)
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Stat
              label="Growth"
              value={formatPctile(ap.growth_percentile)}
              sub="percentile (YoY rev)"
            />
            <Stat
              label="Profitability"
              value={formatPctile(ap.profitability_percentile)}
              sub="percentile (margins)"
            />
            <Stat
              label="Valuation"
              value={formatPctile(ap.valuation_percentile)}
              sub="percentile (P/S or P/E)"
            />
            <Stat
              label="Composite proxy"
              value={formatPctile(ap.composite_proxy_percentile)}
              sub="percentile (blend)"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="rounded-xl border border-[color:var(--line)] px-4 py-3">
            <p className="text-[10px] uppercase tracking-[0.16em] font-mono text-[color:var(--muted)]">
              Industry cohort
            </p>
            <p className="text-sm text-[color:var(--foreground)] mt-2">
              {context.industry_universe_size != null
                ? `${context.industry_universe_size} names`
                : "N/A"}
            </p>
            <p className="text-2xl font-semibold tabular-nums text-[color:var(--accent-2)] mt-1">
              {context.industry_percentile == null
                ? "N/A"
                : `${formatPctile(context.industry_percentile)}/100`}
            </p>
          </div>
          <div className="rounded-xl border border-[color:var(--line)] px-4 py-3">
            <p className="text-[10px] uppercase tracking-[0.16em] font-mono text-[color:var(--muted)]">
              Market benchmark
            </p>
            <p className="text-sm text-[color:var(--foreground)] mt-2">
              {context.market_universe_size != null
                ? `${context.market_universe_size} names`
                : "N/A"}
            </p>
            <p className="text-2xl font-semibold tabular-nums text-[color:var(--accent-2)] mt-1">
              {context.market_percentile == null
                ? "N/A"
                : `${formatPctile(context.market_percentile)}/100`}
            </p>
          </div>
        </div>

        <p className="text-xs text-[color:var(--muted)] leading-relaxed">
          {context.methodology_note}
        </p>
      </div>
    </Card>
  );
}
