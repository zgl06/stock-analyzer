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
}

export default async function AnalysisPage({ params }: AnalysisPageProps) {
  const { ticker } = await params;
  const normalized = ticker.trim().toUpperCase();

  let data;
  try {
    data = await fetchAnalysis(normalized);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      notFound();
    }
    throw error;
  }

  return (
    <div className="max-w-6xl mx-auto px-6 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <Link
          href="/"
          className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
        >
          &larr; New search
        </Link>
        <span className="text-xs px-2 py-1 rounded-full bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200 font-mono uppercase tracking-wider">
          {data.source}
        </span>
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

      <p className="text-xs text-slate-500 dark:text-slate-400 text-center pt-4">
        Methodology version{" "}
        <span className="font-mono">{data.score.methodology_version}</span>
      </p>
    </div>
  );
}
