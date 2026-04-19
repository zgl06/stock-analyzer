import Card from "./Card";
import type { MarketDataSnapshot } from "@/lib/types";
import {
  formatCurrency,
  formatDateTime,
  formatMultiple,
  formatPercent,
} from "@/lib/format";

interface MarketDataCardProps {
  market: MarketDataSnapshot;
}

interface RowProps {
  label: string;
  value: string;
}

function Row({ label, value }: RowProps) {
  return (
    <div className="flex justify-between text-sm py-1.5 border-b border-slate-100 dark:border-slate-800 last:border-0">
      <span className="text-slate-500 dark:text-slate-400">{label}</span>
      <span className="font-mono font-medium">{value}</span>
    </div>
  );
}

export default function MarketDataCard({ market }: MarketDataCardProps) {
  return (
    <Card title="Market data" subtitle={`As of ${formatDateTime(market.as_of)}`}>
      <div className="text-3xl font-semibold mb-4">
        {formatCurrency(market.price_usd, { compact: false, digits: 2 })}
      </div>
      <div className="space-y-0">
        <Row label="Market cap" value={formatCurrency(market.market_cap_usd)} />
        <Row
          label="Enterprise value"
          value={formatCurrency(market.enterprise_value_usd)}
        />
        <Row label="P/E" value={formatMultiple(market.price_to_earnings)} />
        <Row label="P/S" value={formatMultiple(market.price_to_sales)} />
        <Row
          label="Dividend yield"
          value={formatPercent(market.dividend_yield, 2)}
        />
        <Row
          label="52w high"
          value={formatCurrency(market.fifty_two_week_high_usd, {
            compact: false,
            digits: 2,
          })}
        />
        <Row
          label="52w low"
          value={formatCurrency(market.fifty_two_week_low_usd, {
            compact: false,
            digits: 2,
          })}
        />
      </div>
    </Card>
  );
}
