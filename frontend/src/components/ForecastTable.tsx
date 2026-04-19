import Card from "./Card";
import type { ForecastScenario, ScenarioName } from "@/lib/types";
import { formatMultiple, formatPercent, titleCase } from "@/lib/format";

interface ForecastTableProps {
  scenarios: ForecastScenario[];
}

const SCENARIO_STYLES: Record<ScenarioName, string> = {
  bear: "bg-rose-50 dark:bg-rose-950/30 text-rose-700 dark:text-rose-200",
  base: "bg-slate-50 dark:bg-slate-800/50 text-slate-700 dark:text-slate-200",
  bull: "bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-200",
};

export default function ForecastTable({ scenarios }: ForecastTableProps) {
  if (scenarios.length === 0) {
    return (
      <Card title="Forecast scenarios">
        <p className="text-sm text-slate-500 dark:text-slate-400">
          No forecast scenarios available.
        </p>
      </Card>
    );
  }

  return (
    <Card title="Forecast scenarios" subtitle="3-5 year scenario model">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {scenarios.map((scenario) => (
          <div
            key={scenario.scenario}
            className={`rounded-lg p-4 border border-slate-200 dark:border-slate-700 ${SCENARIO_STYLES[scenario.scenario]}`}
          >
            <div className="flex items-baseline justify-between">
              <div className="font-semibold uppercase tracking-wider text-sm">
                {titleCase(scenario.scenario)}
              </div>
              <div className="text-xs opacity-70">
                {scenario.horizon_years}y
              </div>
            </div>
            <dl className="mt-3 space-y-1.5 text-sm">
              <div className="flex justify-between">
                <dt className="opacity-70">Revenue CAGR</dt>
                <dd className="font-mono font-medium">
                  {formatPercent(scenario.revenue_cagr)}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="opacity-70">Op. margin (end)</dt>
                <dd className="font-mono font-medium">
                  {formatPercent(scenario.operating_margin_end)}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="opacity-70">Terminal mult.</dt>
                <dd className="font-mono font-medium">
                  {formatMultiple(scenario.terminal_multiple)}
                </dd>
              </div>
              <div className="flex justify-between pt-1 border-t border-slate-200/50 dark:border-slate-700/50 mt-1">
                <dt className="opacity-70">Annualized return</dt>
                <dd className="font-mono font-semibold">
                  {formatPercent(scenario.expected_annualized_return)}
                </dd>
              </div>
            </dl>
            {scenario.assumptions && (
              <p className="mt-3 text-xs opacity-80 leading-relaxed">
                {scenario.assumptions}
              </p>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}
