import TickerSearch from "@/components/TickerSearch";

const SUGGESTIONS = ["AAPL"];

export default function Home() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-16 sm:py-24">
      <div className="text-center mb-10">
        <h1 className="text-4xl sm:text-5xl font-semibold tracking-tight">
          Long-term equity analysis
        </h1>
        <p className="mt-4 text-slate-600 dark:text-slate-400">
          Enter a US ticker to see a deterministic, explainable scorecard,
          forecast scenarios, and peer comparison.
        </p>
      </div>

      <TickerSearch />

      <div className="mt-8 text-sm text-slate-500 dark:text-slate-400 text-center">
        <span>Try: </span>
        {SUGGESTIONS.map((ticker, idx) => (
          <span key={ticker}>
            <a
              href={`/analysis/${ticker}`}
              className="font-mono text-blue-600 dark:text-blue-400 hover:underline"
            >
              {ticker}
            </a>
            {idx < SUGGESTIONS.length - 1 ? ", " : ""}
          </span>
        ))}
      </div>
    </div>
  );
}
