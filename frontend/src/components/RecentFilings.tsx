import Card from "./Card";
import type { FilingRecord } from "@/lib/types";
import { formatDate } from "@/lib/format";

interface RecentFilingsProps {
  filings: FilingRecord[];
}

const FILING_TYPE_STYLES: Record<FilingRecord["filing_type"], string> = {
  "10-K": "bg-emerald-400/15 text-emerald-300 border-emerald-400/30",
  "10-Q": "bg-teal-400/15 text-teal-300 border-teal-400/30",
  "8-K": "bg-amber-400/15 text-amber-300 border-amber-400/30",
};

export default function RecentFilings({ filings }: RecentFilingsProps) {
  if (filings.length === 0) {
    return (
      <Card eyebrow="Filings" title="Recent SEC filings">
        <p className="text-sm text-[color:var(--muted)]">
          No filings available.
        </p>
      </Card>
    );
  }

  return (
    <Card eyebrow="Filings" title="Recent SEC filings" subtitle="Source: EDGAR">
      <ul className="divide-y divide-[color:var(--line)] -my-3">
        {filings.map((filing) => (
          <li key={filing.accession_number} className="py-3">
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-3 min-w-0">
                <span
                  className={`text-[11px] font-mono px-2 py-0.5 rounded border ${FILING_TYPE_STYLES[filing.filing_type]}`}
                >
                  {filing.filing_type}
                </span>
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate text-[color:var(--foreground)]">
                    {filing.description ??
                      `Filed ${formatDate(filing.filing_date)}`}
                  </div>
                  <div className="text-xs text-[color:var(--muted)] font-mono">
                    {filing.accession_number}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-4 shrink-0">
                <div className="text-xs text-[color:var(--muted)] font-mono whitespace-nowrap">
                  {formatDate(filing.filing_date)}
                </div>
                <a
                  href={filing.primary_document_url ?? filing.filing_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-sm text-[color:var(--accent-2)] hover:text-[color:var(--accent)] underline-offset-4 hover:underline whitespace-nowrap"
                >
                  Open
                  <svg
                    viewBox="0 0 24 24"
                    className="w-3.5 h-3.5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M7 7h10v10" />
                    <path d="M7 17 17 7" />
                  </svg>
                </a>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}
