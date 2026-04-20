import Link from "next/link";

export default function NotFound() {
  return (
    <div className="max-w-2xl mx-auto px-6 py-24 text-center space-y-5">
      <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-[color:var(--line-strong)] bg-[color:var(--surface)] text-xs font-mono uppercase tracking-wider text-[color:var(--accent-2)]">
        <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
        Ticker not recognized
      </div>
      <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight">
        We couldn&apos;t find that ticker
      </h1>
      <p className="text-[color:var(--muted-strong)] leading-relaxed">
        SEC EDGAR doesn&apos;t recognize this symbol. Double-check the spelling
        and try again, or pick a known large-cap like{" "}
        <Link
          href="/analysis/AAPL"
          className="font-mono text-[color:var(--accent-2)] hover:text-[color:var(--accent)] underline-offset-4 hover:underline"
        >
          AAPL
        </Link>
        ,{" "}
        <Link
          href="/analysis/MSFT"
          className="font-mono text-[color:var(--accent-2)] hover:text-[color:var(--accent)] underline-offset-4 hover:underline"
        >
          MSFT
        </Link>
        , or{" "}
        <Link
          href="/analysis/NVDA"
          className="font-mono text-[color:var(--accent-2)] hover:text-[color:var(--accent)] underline-offset-4 hover:underline"
        >
          NVDA
        </Link>
        .
      </p>
      <div className="pt-2">
        <Link
          href="/"
          className="inline-flex items-center gap-2 rounded-full bg-[color:var(--accent)] hover:bg-[color:var(--accent-2)] text-[#04150f] font-medium px-5 py-2.5 text-sm shadow-[0_0_28px_-6px_rgba(52,211,153,0.7)] transition-colors"
        >
          New search
        </Link>
      </div>
    </div>
  );
}
