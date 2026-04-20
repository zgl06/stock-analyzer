import Card from "./Card";
import type { ForecastScenario, ScenarioName } from "@/lib/types";
import { formatMultiple, formatPercent, titleCase } from "@/lib/format";

interface ForecastTableProps {
  scenarios: ForecastScenario[];
}

const SCENARIO_STYLES: Record<ScenarioName, string> = {
  bear: "border-rose-400/30 bg-rose-400/5 text-rose-200",
  base: "border-[color:var(--line-strong)] bg-[color:var(--surface-raised)] text-[color:var(--foreground)]",
  bull: "border-emerald-400/40 bg-emerald-400/8 text-emerald-100 shadow-[0_0_24px_-12px_rgba(52,211,153,0.6)]",
};

const SCENARIO_DOT: Record<ScenarioName, string> = {
  bear: "bg-rose-400",
  base: "bg-teal-400",
  bull: "bg-emerald-400",
};

export default function ForecastTable({ scenarios }: ForecastTableProps) {
  if (scenarios.length === 0) {
    return (
      <Card eyebrow="Forecast" title="Scenario forecasts">
        <p className="text-sm text-[color:var(--muted)]">
          No forecast scenarios available.
        </p>
      </Card>
    );
  }

  return (
    <Card
      eyebrow="Forecast"
      title="Scenario forecasts"
      subtitle="Bear / base / bull, deterministic by construction"
    >
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {scenarios.map((scenario) => (
          <div
            key={scenario.scenario}
            className={`rounded-xl p-4 border ${SCENARIO_STYLES[scenario.scenario]}`}
          >
            <div className="flex items-baseline justify-between">
              <div className="flex items-center gap-2">
                <span
                  className={`w-1.5 h-1.5 rounded-full ${SCENARIO_DOT[scenario.scenario]}`}
                />
                <div className="font-semibold uppercase tracking-wider text-xs font-mono">
                  {titleCase(scenario.scenario)}
                </div>
              </div>
              <div className="text-[10px] font-mono opacity-70">
                {scenario.horizon_years}y
              </div>
            </div>
            <dl className="mt-4 space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="opacity-70">Revenue CAGR</dt>
                <dd className="font-mono font-medium">
                  {formatPercent(scenario.revenue_cagr)}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="opacity-70">Op. profit % (yr 5)</dt>
                <dd className="font-mono font-medium">
                  {formatPercent(scenario.operating_margin_end)}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="opacity-70">Year-5 P/E</dt>
                <dd className="font-mono font-medium">
                  {formatMultiple(scenario.terminal_multiple)}
                </dd>
              </div>
              <div className="flex justify-between pt-2 border-t border-current/15 mt-1">
                <dt className="opacity-70">Annualized return</dt>
                <dd className="font-mono font-semibold">
                  {formatPercent(scenario.expected_annualized_return)}
                </dd>
              </div>
            </dl>
          </div>
        ))}
      </div>
    </Card>
  );
}
