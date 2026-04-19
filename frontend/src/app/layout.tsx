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
  title: "Stock Analyzer",
  description: "Long-term equity analysis dashboard",
};

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
      <body className="min-h-full flex flex-col bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
        <header className="border-b border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-900/70 backdrop-blur sticky top-0 z-10">
          <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
            <Link
              href="/"
              className="font-semibold tracking-tight text-lg hover:opacity-80"
            >
              Stock Analyzer
            </Link>
            <nav className="text-sm text-slate-500 dark:text-slate-400">
              <span className="font-mono">v0.1</span>
            </nav>
          </div>
        </header>
        <main className="flex-1 w-full">{children}</main>
        <footer className="border-t border-slate-200 dark:border-slate-800 py-4 text-xs text-center text-slate-500 dark:text-slate-400">
          Long-term analysis. Not investment advice.
        </footer>
      </body>
    </html>
  );
}
