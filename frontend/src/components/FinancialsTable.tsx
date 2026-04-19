import Card from "./Card";
import type { NormalizedFinancials } from "@/lib/types";
import {
  formatCurrency,
  formatNumber,
  formatPercent,
} from "@/lib/format";

interface FinancialsTableProps {
  financials: NormalizedFinancials;
}

export default function FinancialsTable({ financials }: FinancialsTableProps) {
  const periods = financials.periods;

  if (periods.length === 0) {
    return (
      <Card title="Financials">
        <p className="text-sm text-slate-500 dark:text-slate-400">
          No financial periods available.
        </p>
      </Card>
    );
  }

  return (
    <Card
      title="Financials"
      subtitle={`Reporting basis: ${financials.reporting_basis} · latest ${financials.latest_fiscal_period} ${financials.latest_fiscal_year}`}
    >
      <div className="overflow-x-auto -mx-6">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
              <th className="px-6 py-2 font-medium">Period</th>
              <th className="px-3 py-2 font-medium text-right">Revenue</th>
              <th className="px-3 py-2 font-medium text-right">Net income</th>
              <th className="px-3 py-2 font-medium text-right">EPS</th>
              <th className="px-3 py-2 font-medium text-right">GM</th>
              <th className="px-3 py-2 font-medium text-right">OM</th>
              <th className="px-3 py-2 font-medium text-right">FCF</th>
              <th className="px-3 py-2 font-medium text-right">Cash</th>
              <th className="px-6 py-2 font-medium text-right">Debt</th>
            </tr>
          </thead>
          <tbody>
            {periods.map((period) => (
              <tr
                key={`${period.fiscal_year}-${period.fiscal_period}`}
                className="border-b border-slate-100 dark:border-slate-800 last:border-0"
              >
                <td className="px-6 py-3 font-mono">
                  {period.fiscal_period} {period.fiscal_year}
                </td>
                <td className="px-3 py-3 text-right font-mono">
                  {formatCurrency(period.revenue_usd)}
                </td>
                <td className="px-3 py-3 text-right font-mono">
                  {formatCurrency(period.net_income_usd)}
                </td>
                <td className="px-3 py-3 text-right font-mono">
                  {formatNumber(period.diluted_eps, { compact: false, digits: 2 })}
                </td>
                <td className="px-3 py-3 text-right font-mono">
                  {formatPercent(period.gross_margin)}
                </td>
                <td className="px-3 py-3 text-right font-mono">
                  {formatPercent(period.operating_margin)}
                </td>
                <td className="px-3 py-3 text-right font-mono">
                  {formatCurrency(period.free_cash_flow_usd)}
                </td>
                <td className="px-3 py-3 text-right font-mono">
                  {formatCurrency(period.cash_and_equivalents_usd)}
                </td>
                <td className="px-6 py-3 text-right font-mono">
                  {formatCurrency(period.total_debt_usd)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
