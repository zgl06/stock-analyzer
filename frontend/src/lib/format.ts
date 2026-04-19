export function formatCurrency(
  value: number | null | undefined,
  options: { compact?: boolean; digits?: number } = {},
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  const { compact = true, digits = 1 } = options;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: compact ? "compact" : "standard",
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatNumber(
  value: number | null | undefined,
  options: { compact?: boolean; digits?: number } = {},
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  const { compact = true, digits = 2 } = options;
  return new Intl.NumberFormat("en-US", {
    notation: compact ? "compact" : "standard",
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatPercent(
  value: number | null | undefined,
  digits = 1,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  return new Intl.NumberFormat("en-US", {
    style: "percent",
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(value);
}

export function formatMultiple(
  value: number | null | undefined,
  digits = 1,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  return `${value.toFixed(digits)}x`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "N/A";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toISOString().slice(0, 10);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "N/A";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function titleCase(value: string): string {
  return value
    .split(/[_\s]+/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
