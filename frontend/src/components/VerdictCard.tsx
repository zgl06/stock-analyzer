import Card from "./Card";
import type { InvestmentVerdict, LongTermRating } from "@/lib/types";
import { formatPercent } from "@/lib/format";

interface VerdictCardProps {
  verdict: InvestmentVerdict;
}

const RATING_STYLES: Record<LongTermRating, string> = {
  "Strong Buy":
    "bg-emerald-400/15 text-emerald-300 border-emerald-400/40 shadow-[0_0_24px_-8px_rgba(52,211,153,0.6)]",
  Buy: "bg-teal-400/15 text-teal-300 border-teal-400/40",
  Hold: "bg-amber-400/15 text-amber-300 border-amber-400/40",
  Avoid: "bg-rose-400/15 text-rose-300 border-rose-400/40",
};

export default function VerdictCard({ verdict }: VerdictCardProps) {
  return (
    <Card eyebrow="Verdict" title="Long-term recommendation">
      <div className="space-y-5">
        <div
          className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border text-sm font-semibold tracking-wide ${RATING_STYLES[verdict.rating]}`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-current" />
          {verdict.rating}
        </div>

        <div>
          <div className="text-xs uppercase tracking-wider font-mono text-[color:var(--muted)]">
            Confidence
          </div>
          <div className="mt-1.5 flex items-center gap-3">
            <div className="flex-1 h-1.5 rounded-full bg-[color:var(--surface-raised)] overflow-hidden">
              <div
                className="h-full bg-[color:var(--accent)] shadow-[0_0_8px_-1px_var(--accent)]"
                style={{ width: `${Math.round(verdict.confidence * 100)}%` }}
              />
            </div>
            <span className="text-sm font-mono text-[color:var(--muted-strong)]">
              {Math.round(verdict.confidence * 100)}%
            </span>
          </div>
        </div>

        {(verdict.expected_return_low !== null ||
          verdict.expected_return_high !== null) && (
          <div>
            <div className="text-xs uppercase tracking-wider font-mono text-[color:var(--muted)]">
              Expected annualized return
            </div>
            <div className="mt-1 text-lg font-semibold font-mono text-[color:var(--accent-2)]">
              {formatPercent(verdict.expected_return_low)}
              <span className="text-[color:var(--muted)]"> – </span>
              {formatPercent(verdict.expected_return_high)}
            </div>
          </div>
        )}

        {verdict.summary && (
          <p className="text-sm text-[color:var(--muted-strong)] leading-relaxed border-t border-[color:var(--line)] pt-4">
            {verdict.summary}
          </p>
        )}
      </div>
    </Card>
  );
}
