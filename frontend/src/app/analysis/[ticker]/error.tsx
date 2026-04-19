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
    <div className="max-w-2xl mx-auto px-6 py-24 text-center space-y-4">
      <h1 className="text-2xl font-semibold">Couldn&apos;t load analysis</h1>
      <p className="text-slate-600 dark:text-slate-400 break-words">
        {error.message || "Something went wrong reaching the API."}
      </p>
      <p className="text-xs text-slate-500 dark:text-slate-400">
        Make sure the FastAPI backend is running at{" "}
        <span className="font-mono">
          {process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"}
        </span>
        .
      </p>
      <div className="flex gap-3 justify-center pt-2">
        <button
          onClick={reset}
          className="rounded-lg border border-slate-300 dark:border-slate-700 px-4 py-2 text-sm hover:bg-slate-100 dark:hover:bg-slate-800"
        >
          Try again
        </button>
        <Link
          href="/"
          className="rounded-lg bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 text-sm"
        >
          New search
        </Link>
      </div>
    </div>
  );
}
