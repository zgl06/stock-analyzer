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
    <section className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-baseline gap-3">
            <h1 className="text-3xl font-semibold tracking-tight font-mono">
              {ticker}
            </h1>
            <span className="text-lg text-slate-700 dark:text-slate-300">
              {company.company_name}
            </span>
          </div>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-500 dark:text-slate-400">
            {company.exchange && <span>{company.exchange}</span>}
            {company.sector && <span>· {company.sector}</span>}
            {company.industry && <span>· {company.industry}</span>}
            {company.country && <span>· {company.country}</span>}
            <span>· CIK {company.cik}</span>
          </div>
          {company.website && (
            <a
              href={company.website}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-block text-sm text-blue-600 dark:text-blue-400 hover:underline"
            >
              {company.website}
            </a>
          )}
        </div>
        <div className="text-right text-xs text-slate-500 dark:text-slate-400">
          <div className="uppercase tracking-wider">Generated</div>
          <div className="font-mono mt-0.5">{formatDateTime(generatedAt)}</div>
        </div>
      </div>
    </section>
  );
}
