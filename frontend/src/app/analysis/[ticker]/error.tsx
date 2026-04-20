"use client";

import Link from "next/link";

export default function AnalysisError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="max-w-2xl mx-auto px-6 py-24 text-center space-y-5">
      <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-rose-400/40 bg-rose-400/10 text-xs font-mono uppercase tracking-wider text-rose-300">
        <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
        Analysis failed
      </div>
      <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight">
        Couldn&apos;t load analysis
      </h1>
      <p className="text-[color:var(--muted-strong)] break-words">
        {error.message || "Something went wrong reaching the API."}
      </p>
      <p className="text-xs text-[color:var(--muted)]">
        Make sure the FastAPI backend is running at{" "}
        <span className="font-mono text-[color:var(--accent-2)]">
          {process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"}
        </span>
        .
      </p>
      <div className="flex gap-3 justify-center pt-2">
        <button
          onClick={reset}
          className="rounded-full border border-[color:var(--line-strong)] bg-[color:var(--surface)] hover:border-[color:var(--accent)] px-5 py-2.5 text-sm transition-colors"
        >
          Try again
        </button>
        <Link
          href="/"
          className="rounded-full bg-[color:var(--accent)] hover:bg-[color:var(--accent-2)] text-[#04150f] font-medium px-5 py-2.5 text-sm shadow-[0_0_28px_-6px_rgba(52,211,153,0.7)] transition-colors"
        >
          New search
        </Link>
      </div>
    </div>
  );
}
