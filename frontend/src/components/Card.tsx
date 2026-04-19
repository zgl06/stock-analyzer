import type { ReactNode } from "react";

interface CardProps {
  title?: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
}

export default function Card({
  title,
  subtitle,
  children,
  className = "",
}: CardProps) {
  return (
    <section
      className={`rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm ${className}`}
    >
      {(title || subtitle) && (
        <header className="px-6 py-4 border-b border-slate-200 dark:border-slate-800">
          {title && (
            <h2 className="text-base font-semibold tracking-tight">{title}</h2>
          )}
          {subtitle && (
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              {subtitle}
            </p>
          )}
        </header>
      )}
      <div className="p-6">{children}</div>
    </section>
  );
}
