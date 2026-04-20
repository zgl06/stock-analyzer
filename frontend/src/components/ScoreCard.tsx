import Card from "./Card";
import type { ScoreBreakdown } from "@/lib/types";
import { titleCase } from "@/lib/format";

interface ScoreCardProps {
  score: ScoreBreakdown;
}

function scoreBarColor(value: number): string {
  if (value >= 0.7) return "bg-emerald-400";
  if (value >= 0.5) return "bg-teal-400";
  if (value >= 0.3) return "bg-amber-400";
  return "bg-rose-400";
}

function compositeRing(value: number): string {
  if (value >= 0.7) return "text-emerald-400";
  if (value >= 0.5) return "text-teal-400";
  if (value >= 0.3) return "text-amber-400";
  return "text-rose-400";
}

export default function ScoreCard({ score }: ScoreCardProps) {
  const pct = Math.round(score.composite_score * 100);
  return (
    <Card
      eyebrow="Pillar Scoring"
      title="Composite score"
      subtitle="Weighted blend of pillar scores"
    >
      <div className="flex items-center gap-6 mb-6">
        <div
          className={`relative w-24 h-24 rounded-full grid place-items-center ${compositeRing(
            score.composite_score,
          )}`}
        >
          <svg className="absolute inset-0" viewBox="0 0 36 36">
            <path
              className="text-[color:var(--surface-raised)]"
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
          <span className="text-2xl font-semibold text-[color:var(--foreground)]">
            {pct}
          </span>
        </div>
        <div className="flex-1">
          <div className="text-xs uppercase tracking-wider font-mono text-[color:var(--muted)]">
            Composite
          </div>
          <div className="text-3xl font-semibold tracking-tight">
            {pct}%
            <span className="text-base text-[color:var(--muted)] font-normal">
              {" "}
              / 100%
            </span>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        {score.pillars.map((pillar) => {
          const pillarPct = Math.round(pillar.score * 100);
          return (
            <div key={pillar.pillar}>
              <div className="flex items-baseline justify-between text-sm">
                <div className="font-medium text-[color:var(--foreground)]">
                  {titleCase(pillar.pillar)}
                </div>
                <div className="text-[color:var(--muted)] font-mono">
                  {pillarPct}%
                </div>
              </div>
              <div className="mt-1.5 h-1.5 rounded-full bg-[color:var(--surface-raised)] overflow-hidden">
                <div
                  className={`h-full ${scoreBarColor(pillar.score)} shadow-[0_0_8px_-1px_currentColor]`}
                  style={{ width: `${pillarPct}%` }}
                />
              </div>
              {pillar.rationale && (
                <p className="mt-1.5 text-xs text-[color:var(--muted)]">
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
