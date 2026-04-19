export type ScorePillarName =
  | "business_quality"
  | "growth"
  | "profitability"
  | "balance_sheet"
  | "valuation";

export type LongTermRating = "Strong Buy" | "Buy" | "Hold" | "Avoid";

export type ScenarioName = "bear" | "base" | "bull";

export type GuidanceDirection = "up" | "down" | "flat" | "mixed" | "unknown";

export interface CompanySnapshot {
  ticker: string;
  company_name: string;
  cik: string;
  exchange: string | null;
  sector: string | null;
  industry: string | null;
  currency: "USD";
  country: string | null;
  website: string | null;
}

export interface FinancialPeriod {
  period_end: string;
  fiscal_year: number;
  fiscal_period: "FY" | "Q1" | "Q2" | "Q3" | "Q4" | "TTM";
  revenue_usd: number | null;
  net_income_usd: number | null;
  diluted_eps: number | null;
  gross_margin: number | null;
  operating_margin: number | null;
  free_cash_flow_usd: number | null;
  cash_and_equivalents_usd: number | null;
  total_debt_usd: number | null;
  shares_outstanding: number | null;
  revenue_yoy_growth: number | null;
  net_income_yoy_growth: number | null;
}

export interface NormalizedFinancials {
  reporting_basis: "annual" | "annual_plus_ttm";
  latest_fiscal_year: number;
  latest_fiscal_period: "FY" | "Q1" | "Q2" | "Q3" | "Q4" | "TTM";
  periods: FinancialPeriod[];
}

export interface FilingRecord {
  accession_number: string;
  filing_type: "10-K" | "10-Q" | "8-K";
  filing_date: string;
  period_end: string | null;
  filing_url: string;
  primary_document_url: string | null;
  description: string | null;
  items: string[];
}

export interface MarketDataSnapshot {
  as_of: string;
  price_usd: number;
  market_cap_usd: number | null;
  enterprise_value_usd: number | null;
  price_to_earnings: number | null;
  price_to_sales: number | null;
  dividend_yield: number | null;
  fifty_two_week_high_usd: number | null;
  fifty_two_week_low_usd: number | null;
  historical_prices: number[];
}

export interface AnalysisInput {
  company: CompanySnapshot;
  financials: NormalizedFinancials;
  filings: FilingRecord[];
  marketData: MarketDataSnapshot;
}

export interface PillarScore {
  pillar: ScorePillarName;
  score: number;
  weight: number;
  rationale: string | null;
}

export interface ScoreBreakdown {
  composite_score: number;
  pillars: PillarScore[];
  methodology_version: string;
}

export interface ForecastScenario {
  scenario: ScenarioName;
  horizon_years: number;
  revenue_cagr: number | null;
  operating_margin_end: number | null;
  terminal_multiple: number | null;
  expected_annualized_return: number | null;
  assumptions: string | null;
}

export interface PeerComparison {
  ticker: string;
  company_name: string | null;
  market_cap_usd: number | null;
  revenue_yoy_growth: number | null;
  gross_margin: number | null;
  operating_margin: number | null;
  price_to_earnings: number | null;
  price_to_sales: number | null;
  notes: string | null;
}

export interface DocumentSummary {
  management_tone: string | null;
  guidance_direction: GuidanceDirection;
  top_risks: string[];
  top_positives: string[];
  thesis_paragraph: string | null;
  source_filings: string[];
  available: boolean;
}

export interface InvestmentVerdict {
  rating: LongTermRating;
  confidence: number;
  expected_return_low: number | null;
  expected_return_high: number | null;
  summary: string | null;
}

export interface AnalysisJobStatus {
  ticker: string;
  state: "queued" | "running" | "completed" | "failed";
  created_at: string;
  updated_at: string;
  error_message: string | null;
}

export interface AnalysisResponse {
  ticker: string;
  generated_at: string;
  source: "fixture" | "live";
  company: CompanySnapshot;
  analysis_input: AnalysisInput;
  score: ScoreBreakdown;
  forecast: ForecastScenario[];
  peers: PeerComparison[];
  verdict: InvestmentVerdict;
  document_summary: DocumentSummary | null;
  job: AnalysisJobStatus | null;
}
