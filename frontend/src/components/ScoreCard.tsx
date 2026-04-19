import Card from "./Card";
import type { ScoreBreakdown } from "@/lib/types";
import { titleCase } from "@/lib/format";

interface ScoreCardProps {
  score: ScoreBreakdown;
}

function scoreBarColor(value: number): string {
  if (value >= 0.7) return "bg-emerald-500";
  if (value >= 0.5) return "bg-amber-500";
  if (value >= 0.3) return "bg-orange-500";
  return "bg-rose-500";
}

function compositeRing(value: number): string {
  if (value >= 0.7) return "text-emerald-500";
  if (value >= 0.5) return "text-amber-500";
  if (value >= 0.3) return "text-orange-500";
  return "text-rose-500";
}

export default function ScoreCard({ score }: ScoreCardProps) {
  const pct = Math.round(score.composite_score * 100);
  return (
    <Card title="Composite score" subtitle="Weighted blend of pillar scores">
      <div className="flex items-center gap-6 mb-6">
        <div
          className={`relative w-24 h-24 rounded-full grid place-items-center ${compositeRing(
            score.composite_score,
          )}`}
        >
          <svg className="absolute inset-0" viewBox="0 0 36 36">
            <path
              className="text-slate-200 dark:text-slate-800"
              stroke="currentColor"
              strokeWidth="3"
              fill="none"
              d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
            />
            <path
              stroke="currentColor"
              strokeWidth="3"
              strokeLinecap="round"
              fill="none"
              strokeDasharray={`${pct}, 100`}
              d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
            />
          </svg>
          <span className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
            {pct}
          </span>
        </div>
        <div className="flex-1">
          <div className="text-sm text-slate-500 dark:text-slate-400">
            Composite
          </div>
          <div className="text-3xl font-semibold tracking-tight">
            {score.composite_score.toFixed(2)}
            <span className="text-base text-slate-400 font-normal"> / 1.00</span>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        {score.pillars.map((pillar) => {
          const pillarPct = Math.round(pillar.score * 100);
          return (
            <div key={pillar.pillar}>
              <div className="flex items-baseline justify-between text-sm">
                <div className="font-medium">{titleCase(pillar.pillar)}</div>
                <div className="text-slate-500 dark:text-slate-400 font-mono">
                  {pillar.score.toFixed(2)}
                  <span className="ml-2 text-xs">
                    w {Math.round(pillar.weight * 100)}%
                  </span>
                </div>
              </div>
              <div className="mt-1 h-2 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                <div
                  className={`h-full ${scoreBarColor(pillar.score)}`}
                  style={{ width: `${pillarPct}%` }}
                />
              </div>
              {pillar.rationale && (
                <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">
                  {pillar.rationale}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}
