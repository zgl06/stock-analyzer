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
      className="flex gap-2 max-w-md mx-auto"
      autoComplete="off"
    >
      <input
        type="text"
        value={ticker}
        onChange={(event) => setTicker(event.target.value)}
        placeholder="Ticker (e.g. AAPL)"
        className="flex-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-3 font-mono uppercase tracking-wider focus:outline-none focus:ring-2 focus:ring-blue-500"
        maxLength={8}
      />
      <button
        type="submit"
        disabled={submitting || !ticker.trim()}
        className="rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium px-5 py-3 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {submitting ? "Loading..." : "Analyze"}
      </button>
    </form>
  );
}
