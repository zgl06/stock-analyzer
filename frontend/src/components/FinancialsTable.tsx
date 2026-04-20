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
      <Card eyebrow="Financials" title="Normalized financials">
        <p className="text-sm text-[color:var(--muted)]">
          No financial periods available.
        </p>
      </Card>
    );
  }

  return (
    <Card
      eyebrow="Financials"
      title="Normalized financials"
      subtitle={`${financials.reporting_basis} basis · latest ${financials.latest_fiscal_period} ${financials.latest_fiscal_year}`}
    >
      <div className="overflow-x-auto -mx-6">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[10px] uppercase tracking-[0.18em] font-mono text-[color:var(--muted)] border-b border-[color:var(--line)]">
              <th className="px-6 py-3 font-medium">Period</th>
              <th className="px-3 py-3 font-medium text-right">Revenue</th>
              <th className="px-3 py-3 font-medium text-right">Net income</th>
              <th className="px-3 py-3 font-medium text-right">EPS</th>
              <th className="px-3 py-3 font-medium text-right">GM</th>
              <th className="px-3 py-3 font-medium text-right">OM</th>
              <th className="px-3 py-3 font-medium text-right">FCF</th>
              <th className="px-3 py-3 font-medium text-right">Cash</th>
              <th className="px-6 py-3 font-medium text-right">Debt</th>
            </tr>
          </thead>
          <tbody>
            {periods.map((period) => (
              <tr
                key={`${period.fiscal_year}-${period.fiscal_period}`}
                className="border-b border-[color:var(--line)] last:border-0 hover:bg-[color:var(--surface-raised)] transition-colors"
              >
                <td className="px-6 py-3 font-mono text-[color:var(--accent-2)]">
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
