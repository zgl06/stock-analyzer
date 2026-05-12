-- Migration 001: filing_chunks table and match_filing_chunks RPC
-- Apply via Supabase SQL editor or `supabase db execute --file backend/migrations/001_filing_chunks.sql`

-- Enable the pgvector extension (requires Supabase pg_vector add-on or Postgres 15+).
create extension if not exists vector;

-- -------------------------------------------------------------------------
-- Table: filing_chunks
-- Stores fixed-size overlapping text chunks from SEC filings with embeddings.
-- Embedding dimension: 384 (all-MiniLM-L6-v2).
-- -------------------------------------------------------------------------
create table if not exists filing_chunks (
    id               uuid primary key default gen_random_uuid(),
    company_id       uuid not null references companies(id) on delete cascade,
    accession_number text not null,
    filing_type      text not null,
    filing_date      date not null,
    chunk_index      integer not null,
    text             text not null,
    embedding        vector(384) not null,
    token_count      integer not null default 0,
    created_at       timestamptz not null default now()
);

-- HNSW index for fast approximate cosine similarity search.
-- ef_construction=64 and m=16 are conservative defaults suitable for a
-- dataset of millions of chunks; tune upward if recall is insufficient.
create index if not exists filing_chunks_embedding_hnsw
    on filing_chunks
    using hnsw (embedding vector_cosine_ops)
    with (m = 16, ef_construction = 64);

-- Btree index to filter by company before the vector scan.
create index if not exists filing_chunks_company_accession
    on filing_chunks (company_id, accession_number);

-- -------------------------------------------------------------------------
-- RPC function: match_filing_chunks
-- Returns top match_count chunks for a company ordered by cosine similarity.
-- Called as: supabase.rpc("match_filing_chunks", {...})
-- -------------------------------------------------------------------------
create or replace function match_filing_chunks(
    query_embedding  vector(384),
    match_count      integer,
    p_company_id     uuid
)
returns table (
    id               uuid,
    accession_number text,
    filing_type      text,
    filing_date      date,
    text             text,
    token_count      integer,
    score            float
)
language sql stable
as $$
    select
        fc.id,
        fc.accession_number,
        fc.filing_type,
        fc.filing_date,
        fc.text,
        fc.token_count,
        1 - (fc.embedding <=> query_embedding) as score
    from filing_chunks fc
    where fc.company_id = p_company_id
    order by fc.embedding <=> query_embedding
    limit match_count;
$$;
