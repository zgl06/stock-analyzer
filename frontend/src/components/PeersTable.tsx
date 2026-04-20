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
      <Card eyebrow="Peers" title="Peer comparison">
        <p className="text-sm text-[color:var(--muted)]">No peers available.</p>
      </Card>
    );
  }

  return (
    <Card
      eyebrow="Peers"
      title="Peer comparison"
      subtitle="Comparable companies side by side"
    >
      <div className="overflow-x-auto -mx-6">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[10px] uppercase tracking-[0.18em] font-mono text-[color:var(--muted)] border-b border-[color:var(--line)]">
              <th className="px-6 py-3 font-medium">Ticker</th>
              <th className="px-3 py-3 font-medium">Company</th>
              <th className="px-3 py-3 font-medium text-right">Mkt cap</th>
              <th className="px-3 py-3 font-medium text-right">Rev YoY</th>
              <th className="px-3 py-3 font-medium text-right">GM</th>
              <th className="px-3 py-3 font-medium text-right">OM</th>
              <th className="px-3 py-3 font-medium text-right">P/E</th>
              <th className="px-6 py-3 font-medium text-right">P/S</th>
            </tr>
          </thead>
          <tbody>
            {peers.map((peer) => (
              <tr
                key={peer.ticker}
                className="border-b border-[color:var(--line)] last:border-0 hover:bg-[color:var(--surface-raised)] transition-colors"
              >
                <td className="px-6 py-3 font-mono font-semibold text-[color:var(--accent-2)]">
                  {peer.ticker}
                </td>
                <td className="px-3 py-3 text-[color:var(--muted-strong)]">
                  {peer.company_name ?? "—"}
                </td>
                <td className="px-3 py-3 text-right font-mono text-[color:var(--foreground)]">
                  {formatCurrency(peer.market_cap_usd)}
                </td>
                <td className="px-3 py-3 text-right font-mono text-[color:var(--foreground)]">
                  {formatPercent(peer.revenue_yoy_growth)}
                </td>
                <td className="px-3 py-3 text-right font-mono text-[color:var(--foreground)]">
                  {formatPercent(peer.gross_margin)}
                </td>
                <td className="px-3 py-3 text-right font-mono text-[color:var(--foreground)]">
                  {formatPercent(peer.operating_margin)}
                </td>
                <td className="px-3 py-3 text-right font-mono text-[color:var(--foreground)]">
                  {formatMultiple(peer.price_to_earnings)}
                </td>
                <td className="px-6 py-3 text-right font-mono text-[color:var(--foreground)]">
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
