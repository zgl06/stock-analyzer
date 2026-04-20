import type { CompanySnapshot } from "@/lib/types";
import { formatDateTime } from "@/lib/format";

interface CompanyHeaderProps {
  company: CompanySnapshot;
  ticker: string;
  generatedAt: string;
}

export default function CompanyHeader({
  company,
  ticker,
  generatedAt,
}: CompanyHeaderProps) {
  return (
    <section className="surface-strong rounded-2xl p-6 sm:p-8">
      <div className="flex flex-wrap items-start justify-between gap-6">
        <div className="min-w-0">
          <div className="flex items-baseline flex-wrap gap-x-4 gap-y-1">
            <h1 className="text-4xl sm:text-5xl font-semibold tracking-tight font-mono text-gradient-accent">
              {ticker}
            </h1>
            <span className="text-lg sm:text-xl text-[color:var(--muted-strong)]">
              {company.company_name}
            </span>
          </div>
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm text-[color:var(--muted)]">
            {company.exchange && (
              <span className="font-mono uppercase tracking-wider">
                {company.exchange}
              </span>
            )}
            {company.sector && <span>· {company.sector}</span>}
            {company.industry && <span>· {company.industry}</span>}
            {company.country && <span>· {company.country}</span>}
            <span>
              · CIK <span className="font-mono">{company.cik}</span>
            </span>
          </div>
          {company.website && (
            <a
              href={company.website}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-3 inline-flex items-center gap-1.5 text-sm text-[color:var(--accent-2)] hover:text-[color:var(--accent)] underline-offset-4 hover:underline"
            >
              {company.website}
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
          )}
        </div>
        <div className="text-right">
          <div className="text-[10px] uppercase tracking-[0.18em] text-[color:var(--muted)] font-mono">
            Generated
          </div>
          <div className="font-mono text-sm mt-1 text-[color:var(--muted-strong)]">
            {formatDateTime(generatedAt)}
          </div>
        </div>
      </div>
    </section>
  );
}
