import Card from "./Card";
import type { FilingRecord } from "@/lib/types";
import { formatDate } from "@/lib/format";

interface RecentFilingsProps {
  filings: FilingRecord[];
}

const FILING_TYPE_STYLES: Record<FilingRecord["filing_type"], string> = {
  "10-K": "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200",
  "10-Q":
    "bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-200",
  "8-K": "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200",
};

export default function RecentFilings({ filings }: RecentFilingsProps) {
  if (filings.length === 0) {
    return (
      <Card title="Recent filings">
        <p className="text-sm text-slate-500 dark:text-slate-400">
          No filings available.
        </p>
      </Card>
    );
  }

  return (
    <Card title="Recent filings" subtitle="SEC EDGAR">
      <ul className="divide-y divide-slate-100 dark:divide-slate-800 -my-3">
        {filings.map((filing) => (
          <li key={filing.accession_number} className="py-3">
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-3 min-w-0">
                <span
                  className={`text-xs font-mono px-2 py-0.5 rounded ${FILING_TYPE_STYLES[filing.filing_type]}`}
                >
                  {filing.filing_type}
                </span>
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">
                    {filing.description ?? `Filed ${formatDate(filing.filing_date)}`}
                  </div>
                  <div className="text-xs text-slate-500 dark:text-slate-400 font-mono">
                    {filing.accession_number}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-4 shrink-0">
                <div className="text-xs text-slate-500 dark:text-slate-400 font-mono whitespace-nowrap">
                  {formatDate(filing.filing_date)}
                </div>
                <a
                  href={filing.primary_document_url ?? filing.filing_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-blue-600 dark:text-blue-400 hover:underline whitespace-nowrap"
                >
                  Open &rarr;
                </a>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}
