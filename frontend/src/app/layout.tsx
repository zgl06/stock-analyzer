import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Stock Analyzer — Deterministic equity analysis",
  description:
    "AI screeners suggest. Stock Analyzer ships verdicts. Deterministic, explainable, source-of-truth equity analysis.",
};

const NAV_LINKS = [
  { href: "/#capabilities", label: "Capabilities" },
  { href: "/#workflow", label: "Workflow" },
  { href: "/#examples", label: "Examples" },
];

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <header className="sticky top-0 z-20 border-b border-[color:var(--line)] bg-[color:var(--background)]/70 backdrop-blur-md">
          <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2.5 group">
              <span className="grid place-items-center w-7 h-7 rounded-md bg-gradient-to-br from-emerald-400 to-teal-500 shadow-[0_0_18px_-2px_rgba(52,211,153,0.6)]">
                <svg
                  viewBox="0 0 24 24"
                  className="w-4 h-4 text-[#04150f]"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M3 17l5-5 4 4 8-9" />
                  <path d="M14 7h6v6" />
                </svg>
              </span>
              <span className="font-mono text-[13px] tracking-[0.18em] uppercase text-[color:var(--foreground)] group-hover:text-[color:var(--accent-2)] transition-colors">
                Stock Analyzer
              </span>
            </Link>

            <nav className="hidden md:flex items-center gap-7 text-sm text-[color:var(--muted-strong)]">
              {NAV_LINKS.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  className="hover:text-[color:var(--foreground)] transition-colors"
                >
                  {link.label}
                </a>
              ))}
            </nav>

            <div className="flex items-center gap-3">
              <span className="hidden sm:inline-flex items-center gap-1.5 text-[11px] font-mono uppercase tracking-wider text-[color:var(--accent-2)] px-2.5 py-1 rounded-full border border-[color:var(--line-strong)] bg-[color:var(--surface)]">
                <span className="w-1.5 h-1.5 rounded-full bg-[color:var(--accent)] shadow-[0_0_8px_var(--accent-glow)]" />
                Beta
              </span>
              <Link
                href="/#cta"
                className="text-sm font-medium px-3.5 py-1.5 rounded-full bg-[color:var(--accent)] text-[#04150f] hover:bg-[color:var(--accent-2)] transition-colors shadow-[0_0_24px_-6px_rgba(52,211,153,0.6)]"
              >
                Analyze a ticker
              </Link>
            </div>
          </div>
        </header>

        <main className="flex-1 w-full">{children}</main>

        <footer className="border-t border-[color:var(--line)] mt-24">
          <div className="max-w-7xl mx-auto px-6 py-10 grid gap-8 sm:grid-cols-2 lg:grid-cols-4 text-sm">
            <div>
              <div className="flex items-center gap-2.5 mb-3">
                <span className="grid place-items-center w-6 h-6 rounded-md bg-gradient-to-br from-emerald-400 to-teal-500">
                  <svg
                    viewBox="0 0 24 24"
                    className="w-3.5 h-3.5 text-[#04150f]"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M3 17l5-5 4 4 8-9" />
                    <path d="M14 7h6v6" />
                  </svg>
                </span>
                <span className="font-mono uppercase tracking-[0.18em] text-xs">
                  Stock Analyzer
                </span>
              </div>
              <p className="text-[color:var(--muted)] leading-relaxed">
                Deterministic, explainable equity analysis for long-term investors.
              </p>
            </div>
            <div>
              <h4 className="text-xs uppercase tracking-wider text-[color:var(--muted)] mb-3">
                Platform
              </h4>
              <ul className="space-y-2">
                <li>
                  <a
                    href="/#capabilities"
                    className="hover:text-[color:var(--accent-2)] transition-colors"
                  >
                    Capabilities
                  </a>
                </li>
                <li>
                  <a
                    href="/#workflow"
                    className="hover:text-[color:var(--accent-2)] transition-colors"
                  >
                    Workflow
                  </a>
                </li>
              </ul>
            </div>
            <div>
              <h4 className="text-xs uppercase tracking-wider text-[color:var(--muted)] mb-3">
                Data
              </h4>
              <ul className="space-y-2 text-[color:var(--muted-strong)]">
                <li>SEC EDGAR filings</li>
                <li>Yahoo Finance market data</li>
              </ul>
            </div>
            <div>
              <h4 className="text-xs uppercase tracking-wider text-[color:var(--muted)] mb-3">
                Legal
              </h4>
              <p className="text-[color:var(--muted)] leading-relaxed">
                Long-term analysis. Not investment advice.
              </p>
            </div>
          </div>
          <div className="border-t border-[color:var(--line)]">
            <div className="max-w-7xl mx-auto px-6 py-4 text-xs text-[color:var(--muted)] flex flex-wrap items-center justify-between gap-2">
              <span>© 2026 Stock Analyzer. All rights reserved.</span>
              <span className="font-mono">v0.1 · methodology deterministic-v1</span>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
