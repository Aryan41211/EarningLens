# DATASETS.md

## Storage engine

SQLite 3, single file at `data/earningslens.db` (gitignored). No separate
migration/schema files — schema is created inline in `init_db()`.

## Schema

### `transcripts`

```sql
CREATE TABLE transcripts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    company       TEXT NOT NULL,
    quarter       TEXT NOT NULL,        -- "Q1".."Q4"
    year          INTEGER NOT NULL,
    chunk_index   INTEGER NOT NULL,
    chunk_text    TEXT NOT NULL,
    word_count    INTEGER NOT NULL,
    source_file   TEXT NOT NULL,
    extracted_at  TEXT NOT NULL,        -- ISO 8601
    UNIQUE(company, quarter, year, chunk_index)
);
```

Stale chunks for a given `(company, quarter, year)` are deleted before
re-insert, so re-running Phase 1 on an updated PDF is idempotent.

### `scoring_runs`

```sql
CREATE TABLE scoring_runs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id     INTEGER NOT NULL,   -- references transcripts.id
                                           -- (not a formally enforced FK)
    model_name        TEXT NOT NULL,
    prompt_version    TEXT NOT NULL,
    scored_at         TEXT NOT NULL,      -- ISO 8601
    raw_llm_response  TEXT NOT NULL       -- full JSON, for audit trail
);
```

> Note: per-dimension scores are **not yet in a queryable column** — they
> live inside `raw_llm_response` as JSON. A dedicated `scores` table is a
> known gap; see `PROJECT_MEMORY.md` technical debt and `ROADMAP.md`.

## Current data inventory

- 11 processed transcripts: 7 TCS, 4 Infosys (INFY)
- Coverage: Q1 2023 through Q4 2025
- `COMPANIES = ["TCS", "INFY", "WIPRO", "HDFCBANK"]` is declared in
  `config.py` but Wipro/HDFC Bank have no transcripts ingested yet, and the
  list isn't enforced anywhere in the pipeline.

## Input data conventions

- Source: PDFs dropped into `data/raw_pdfs/` (gitignored, never committed)
- Required filename format: `COMPANY_Q<n>_<year>.pdf`, validated against
  `^([A-Za-z0-9&]+)_(Q[1-4])_(\d{4})$`
- Files below 50 extracted words are rejected as likely empty/corrupt
- Cleaned text is written to `data/processed/` for manual inspection —
  this is the easiest way to sanity-check extraction without touching SQLite

## Labeled data (for future evaluation)

`notebooks/reading-notes.md` is a template intended to become a
human-labeled test set for validating Phase 2 LLM scores — currently empty.
`data/findings/findings.md` is a template for one verified
trend-to-stock-move case study — also currently empty. Both are tracked as
open items in `ROADMAP.md`.
