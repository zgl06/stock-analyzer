import Card from "./Card";
import type { InvestmentVerdict, LongTermRating } from "@/lib/types";
import { formatPercent } from "@/lib/format";

interface VerdictCardProps {
  verdict: InvestmentVerdict;
}

const RATING_STYLES: Record<LongTermRating, string> = {
  "Strong Buy":
    "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200",
  Buy: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-200",
  Hold: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200",
  Avoid: "bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-200",
};

export default function VerdictCard({ verdict }: VerdictCardProps) {
  return (
    <Card title="Verdict" subtitle="Long-term recommendation">
      <div className="space-y-4">
        <div
          className={`inline-block px-3 py-1.5 rounded-full text-sm font-semibold ${RATING_STYLES[verdict.rating]}`}
        >
          {verdict.rating}
        </div>

        <div>
          <div className="text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400">
            Confidence
          </div>
          <div className="mt-1 flex items-center gap-3">
            <div className="flex-1 h-2 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
              <div
                className="h-full bg-blue-500"
                style={{ width: `${Math.round(verdict.confidence * 100)}%` }}
              />
            </div>
            <span className="text-sm font-mono text-slate-600 dark:text-slate-300">
              {Math.round(verdict.confidence * 100)}%
            </span>
          </div>
        </div>

        {(verdict.expected_return_low !== null ||
          verdict.expected_return_high !== null) && (
          <div>
            <div className="text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Expected annualized return
            </div>
            <div className="mt-1 text-lg font-semibold">
              {formatPercent(verdict.expected_return_low)}
              <span className="text-slate-400"> – </span>
              {formatPercent(verdict.expected_return_high)}
            </div>
          </div>
        )}

        {verdict.summary && (
          <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
            {verdict.summary}
          </p>
        )}
      </div>
    </Card>
  );
}
