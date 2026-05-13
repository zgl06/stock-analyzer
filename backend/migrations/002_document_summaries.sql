-- Migration 002: document_summaries table
-- Caches LLM-generated qualitative summaries (DocumentSummary) per company,
-- prompt version, and model.  One row per (company, prompt_version, model_name);
-- upsert replaces the payload on re-run so stale rows are never left behind.
-- Apply via Supabase SQL editor or:
--   supabase db execute --file backend/migrations/002_document_summaries.sql

-- -------------------------------------------------------------------------
-- Table: document_summaries
-- -------------------------------------------------------------------------
create table if not exists document_summaries (
    id             uuid primary key default gen_random_uuid(),
    company_id     uuid not null references companies(id) on delete cascade,
    prompt_version text not null,
    model_name     text not null,
    payload        jsonb not null,
    created_at     timestamptz not null default now()
);

-- One cached summary per (company, prompt version, model).
-- ON CONFLICT target for the upsert path.
create unique index if not exists document_summaries_company_prompt_model
    on document_summaries (company_id, prompt_version, model_name);

-- Fast lookup of the latest summary for a company.
create index if not exists document_summaries_company_created
    on document_summaries (company_id, created_at desc);
