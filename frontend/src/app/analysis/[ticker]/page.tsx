import Link from "next/link";
import { notFound } from "next/navigation";

import CompanyHeader from "@/components/CompanyHeader";
import FinancialsTable from "@/components/FinancialsTable";
import ForecastTable from "@/components/ForecastTable";
import MarketDataCard from "@/components/MarketDataCard";
import PeersTable from "@/components/PeersTable";
import RecentFilings from "@/components/RecentFilings";
import ScoreCard from "@/components/ScoreCard";
import VerdictCard from "@/components/VerdictCard";
import { ApiError, fetchAnalysis } from "@/lib/api";

interface AnalysisPageProps {
  params: Promise<{ ticker: string }>;
  searchParams: Promise<{ refresh?: string }>;
}

const SOURCE_STYLES: Record<string, string> = {
  fixture: "border-amber-400/40 bg-amber-400/10 text-amber-300",
  live: "border-emerald-400/40 bg-emerald-400/10 text-emerald-300",
};

export default async function AnalysisPage({
  params,
  searchParams,
}: AnalysisPageProps) {
  const { ticker } = await params;
  const { refresh } = await searchParams;
  const normalized = ticker.trim().toUpperCase();
  const wantRefresh = refresh === "true" || refresh === "1";

  let data;
  try {
    data = await fetchAnalysis(normalized, { refresh: wantRefresh });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      notFound();
    }
    throw error;
  }

  const sourceStyle = SOURCE_STYLES[data.source] ?? SOURCE_STYLES.live;

  return (
    <div className="max-w-6xl mx-auto px-6 py-10 space-y-6">
      <div className="flex items-center justify-between">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-sm text-[color:var(--muted-strong)] hover:text-[color:var(--accent-2)] transition-colors"
        >
          <svg
            viewBox="0 0 24 24"
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="m15 18-6-6 6-6" />
          </svg>
          New search
        </Link>
        <div className="flex items-center gap-3">
          {data.source !== "fixture" && (
            <Link
              href={`/analysis/${normalized}?refresh=true`}
              prefetch={false}
              className="inline-flex items-center gap-1.5 text-[10px] uppercase tracking-[0.18em] font-mono px-2.5 py-1 rounded-full border border-[color:var(--line-strong)] text-[color:var(--muted-strong)] hover:text-[color:var(--accent-2)] hover:border-[color:var(--accent-2)]/50 transition-colors"
              title="Bypass cache and re-ingest live data"
            >
              <svg
                viewBox="0 0 24 24"
                className="w-3 h-3"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.25"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M3 12a9 9 0 0 1 15.5-6.36L21 8" />
                <path d="M21 3v5h-5" />
                <path d="M21 12a9 9 0 0 1-15.5 6.36L3 16" />
                <path d="M3 21v-5h5" />
              </svg>
              Refresh data
            </Link>
          )}
          <span
            className={`inline-flex items-center gap-1.5 text-[10px] uppercase tracking-[0.18em] font-mono px-2.5 py-1 rounded-full border ${sourceStyle}`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-current" />
            {data.source}
          </span>
        </div>
      </div>

      <CompanyHeader
        company={data.company}
        ticker={data.ticker}
        generatedAt={data.generated_at}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <ScoreCard score={data.score} />
        </div>
        <div className="lg:col-span-1">
          <VerdictCard verdict={data.verdict} />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <ForecastTable scenarios={data.forecast} />
        </div>
        <div className="lg:col-span-1">
          <MarketDataCard market={data.analysis_input.marketData} />
        </div>
      </div>

      <PeersTable peers={data.peers} />

      <FinancialsTable financials={data.analysis_input.financials} />

      <RecentFilings filings={data.analysis_input.filings} />

      <p className="text-xs text-[color:var(--muted)] text-center pt-4 font-mono">
        methodology version{" "}
        <span className="text-[color:var(--accent-2)]">
          {data.score.methodology_version}
        </span>
      </p>
    </div>
  );
}
