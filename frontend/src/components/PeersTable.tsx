import Card from "./Card";
import type { PeerComparison } from "@/lib/types";
import {
  formatCurrency,
  formatMultiple,
  formatPercent,
} from "@/lib/format";

interface PeersTableProps {
  peers: PeerComparison[];
}

export default function PeersTable({ peers }: PeersTableProps) {
  if (peers.length === 0) {
    return (
      <Card title="Peer comparison">
        <p className="text-sm text-slate-500 dark:text-slate-400">
          No peers available.
        </p>
      </Card>
    );
  }

  return (
    <Card title="Peer comparison" subtitle="Comparable companies">
      <div className="overflow-x-auto -mx-6">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
              <th className="px-6 py-2 font-medium">Ticker</th>
              <th className="px-3 py-2 font-medium">Company</th>
              <th className="px-3 py-2 font-medium text-right">Mkt cap</th>
              <th className="px-3 py-2 font-medium text-right">Rev YoY</th>
              <th className="px-3 py-2 font-medium text-right">GM</th>
              <th className="px-3 py-2 font-medium text-right">OM</th>
              <th className="px-3 py-2 font-medium text-right">P/E</th>
              <th className="px-6 py-2 font-medium text-right">P/S</th>
            </tr>
          </thead>
          <tbody>
            {peers.map((peer) => (
              <tr
                key={peer.ticker}
                className="border-b border-slate-100 dark:border-slate-800 last:border-0"
              >
                <td className="px-6 py-3 font-mono font-semibold">
                  {peer.ticker}
                </td>
                <td className="px-3 py-3 text-slate-600 dark:text-slate-300">
                  {peer.company_name ?? "—"}
                </td>
                <td className="px-3 py-3 text-right font-mono">
                  {formatCurrency(peer.market_cap_usd)}
                </td>
                <td className="px-3 py-3 text-right font-mono">
                  {formatPercent(peer.revenue_yoy_growth)}
                </td>
                <td className="px-3 py-3 text-right font-mono">
                  {formatPercent(peer.gross_margin)}
                </td>
                <td className="px-3 py-3 text-right font-mono">
                  {formatPercent(peer.operating_margin)}
                </td>
                <td className="px-3 py-3 text-right font-mono">
                  {formatMultiple(peer.price_to_earnings)}
                </td>
                <td className="px-6 py-3 text-right font-mono">
                  {formatMultiple(peer.price_to_sales)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
