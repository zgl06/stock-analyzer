import Link from "next/link";

export default function NotFound() {
  return (
    <div className="max-w-2xl mx-auto px-6 py-24 text-center space-y-4">
      <h1 className="text-2xl font-semibold">Ticker not found</h1>
      <p className="text-slate-600 dark:text-slate-400">
        We don&apos;t have analysis input for that ticker yet. Right now only
        fixture data is wired up (try{" "}
        <span className="font-mono">AAPL</span>).
      </p>
      <Link
        href="/"
        className="inline-block rounded-lg bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 text-sm"
      >
        New search
      </Link>
    </div>
  );
}
