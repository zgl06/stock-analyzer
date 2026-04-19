import type { AnalysisResponse } from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

export async function fetchAnalysis(ticker: string): Promise<AnalysisResponse> {
  const normalized = ticker.trim().toUpperCase();
  const url = `${API_BASE_URL}/analysis/${encodeURIComponent(normalized)}`;

  const response = await fetch(url, {
    cache: "no-store",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const body = await response.json();
      if (body && typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // ignore body parse errors and fall back to default message
    }
    throw new ApiError(detail, response.status);
  }

  return (await response.json()) as AnalysisResponse;
}
