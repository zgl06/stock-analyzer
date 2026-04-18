create extension if not exists pgcrypto;

create table if not exists companies (
    id uuid primary key default gen_random_uuid(),
    ticker text not null unique,
    company_name text not null,
    cik text not null unique,
    exchange text null,
    sector text null,
    industry text null,
    country text null,
    website text null,
    currency text not null default 'USD',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists raw_filings (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references companies(id) on delete cascade,
    accession_number text not null unique,
    filing_type text not null,
    filing_date date not null,
    period_end date null,
    filing_url text not null,
    primary_document_url text null,
    description text null,
    items jsonb not null default '[]'::jsonb,
    raw_payload jsonb not null,
    created_at timestamptz not null default now()
);

create table if not exists raw_market_data (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references companies(id) on delete cascade,
    provider text not null,
    as_of timestamptz not null,
    raw_payload jsonb not null,
    created_at timestamptz not null default now(),
    unique (company_id, provider, as_of)
);

create table if not exists normalized_financial_periods (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references companies(id) on delete cascade,
    period_end date not null,
    fiscal_year integer not null,
    fiscal_period text not null,
    reporting_basis text not null,
    revenue_usd numeric null,
    net_income_usd numeric null,
    diluted_eps numeric null,
    gross_margin numeric null,
    operating_margin numeric null,
    free_cash_flow_usd numeric null,
    cash_and_equivalents_usd numeric null,
    total_debt_usd numeric null,
    shares_outstanding numeric null,
    revenue_yoy_growth numeric null,
    net_income_yoy_growth numeric null,
    source_filing_accession text null,
    created_at timestamptz not null default now(),
    unique (company_id, period_end, fiscal_period)
);

create table if not exists market_data_snapshots (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references companies(id) on delete cascade,
    as_of timestamptz not null,
    price_usd numeric not null,
    market_cap_usd numeric null,
    enterprise_value_usd numeric null,
    price_to_earnings numeric null,
    price_to_sales numeric null,
    dividend_yield numeric null,
    fifty_two_week_high_usd numeric null,
    fifty_two_week_low_usd numeric null,
    historical_prices jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists analysis_inputs (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references companies(id) on delete cascade,
    generated_at timestamptz not null default now(),
    schema_version text not null,
    input_payload jsonb not null,
    is_latest boolean not null default true,
    created_at timestamptz not null default now()
);

create index if not exists idx_companies_ticker on companies (ticker);
create index if not exists idx_raw_filings_company_filing_date on raw_filings (company_id, filing_date desc);
create index if not exists idx_normalized_financial_periods_company_period_end on normalized_financial_periods (company_id, period_end desc);
create index if not exists idx_market_data_snapshots_company_as_of on market_data_snapshots (company_id, as_of desc);
create index if not exists idx_analysis_inputs_company_generated_at on analysis_inputs (company_id, generated_at desc);
