"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export default function TickerSearch() {
  const router = useRouter();
  const [ticker, setTicker] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = ticker.trim().toUpperCase();
    if (!trimmed) return;
    setSubmitting(true);
    router.push(`/analysis/${encodeURIComponent(trimmed)}`);
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col sm:flex-row gap-2 w-full"
      autoComplete="off"
    >
      <div className="relative flex-1">
        <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[color:var(--muted)]">
          <svg
            viewBox="0 0 24 24"
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <circle cx="11" cy="11" r="7" />
            <path d="m21 21-4.3-4.3" />
          </svg>
        </span>
        <input
          type="text"
          value={ticker}
          onChange={(event) => setTicker(event.target.value)}
          placeholder="Enter a US ticker (e.g. AAPL, MSFT, NVDA)"
          className="w-full rounded-full border border-[color:var(--line-strong)] bg-[color:var(--surface)] pl-11 pr-4 py-3.5 font-mono uppercase tracking-wider text-[color:var(--foreground)] placeholder:text-[color:var(--muted)] placeholder:normal-case placeholder:tracking-normal focus:outline-none focus:border-[color:var(--accent)] focus:ring-2 focus:ring-[color:var(--accent)]/30 transition"
          maxLength={8}
          aria-label="Ticker symbol"
        />
      </div>
      <button
        type="submit"
        disabled={submitting || !ticker.trim()}
        className="inline-flex items-center justify-center gap-2 rounded-full bg-[color:var(--accent)] hover:bg-[color:var(--accent-2)] text-[#04150f] font-medium px-6 py-3.5 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-[0_0_28px_-6px_rgba(52,211,153,0.7)]"
      >
        {submitting ? (
          <>
            <span className="w-4 h-4 border-2 border-[#04150f]/30 border-t-[#04150f] rounded-full animate-spin" />
            Loading
          </>
        ) : (
          <>
            Run analysis
            <svg
              viewBox="0 0 24 24"
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M5 12h14" />
              <path d="m12 5 7 7-7 7" />
            </svg>
          </>
        )}
      </button>
    </form>
  );
}
