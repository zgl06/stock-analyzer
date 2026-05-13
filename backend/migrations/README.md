# Migrations

SQL migration files for the stock-analyzer Supabase project.

## How to apply

### Option A — Supabase SQL editor (simplest)
1. Open your Supabase project dashboard.
2. Go to **SQL Editor** > **New query**.
3. Paste the contents of the migration file and click **Run**.

### Option B — Supabase CLI
```bash
supabase db push
```
or, for a one-off file:
```bash
supabase db execute --file backend/migrations/001_filing_chunks.sql
```

## File naming
Files are prefixed with a zero-padded sequence number: `001_`, `002_`, ...
Run them in order; each is idempotent (`CREATE ... IF NOT EXISTS`, `IF NOT EXISTS` guards).

## Migrations

| File | Description |
|------|-------------|
| `001_filing_chunks.sql` | `filing_chunks` table + `match_filing_chunks` RPC for RAG (L1). |
| `002_document_summaries.sql` | `document_summaries` table for caching qualitative LLM summaries (L3). |
