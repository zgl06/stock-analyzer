import type { ReactNode } from "react";

interface CardProps {
  title?: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
  eyebrow?: string;
}

export default function Card({
  title,
  subtitle,
  children,
  className = "",
  eyebrow,
}: CardProps) {
  return (
    <section
      className={`surface rounded-2xl overflow-hidden ${className}`}
    >
      {(title || subtitle || eyebrow) && (
        <header className="px-6 py-4 border-b border-[color:var(--line)]">
          {eyebrow && (
            <div className="text-[10px] uppercase tracking-[0.18em] font-mono text-[color:var(--accent-2)] mb-1">
              {eyebrow}
            </div>
          )}
          {title && (
            <h2 className="text-base font-semibold tracking-tight text-[color:var(--foreground)]">
              {title}
            </h2>
          )}
          {subtitle && (
            <p className="text-sm text-[color:var(--muted)] mt-1">
              {subtitle}
            </p>
          )}
        </header>
      )}
      <div className="p-6">{children}</div>
    </section>
  );
}
