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

### `scores`

The queryable per-dimension table. Added after the `scoring_runs`-only design;
this is what the trend layer and dashboard read.

```sql
CREATE TABLE scores (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id     INTEGER NOT NULL,   -- rowid of chunk 0; convenience only
    company           TEXT,               --     quarter           TEXT,               --  } the stable identity
    year              INTEGER,            -- /
    dimension         TEXT NOT NULL,      -- one of config.SCORE_DIMENSIONS
    score             INTEGER NOT NULL,   -- 1-10, higher = worse
    supporting_quotes TEXT,               -- JSON array, max 3
    scored_at         TEXT NOT NULL,      -- ISO 8601
    model_name        TEXT NOT NULL,
    prompt_version    TEXT NOT NULL,      -- currently always "<dimension>-v1"
    raw_llm_response  TEXT NOT NULL,
    FOREIGN KEY (transcript_id) REFERENCES transcripts(id),
    UNIQUE(transcript_id, dimension)
);

CREATE UNIQUE INDEX idx_scores_identity
    ON scores(company, quarter, year, dimension);
```

`INSERT OR REPLACE` plus the identity index makes re-scoring idempotent even
across a re-ingest.

> **Why the identity columns exist.** `transcripts` holds one row per *chunk*,
> so there is no transcript-level row to reference; `transcript_id` is the rowid
> of that transcript's `chunk_index = 0`. `store_transcript()` deletes and
> re-inserts chunks and `AUTOINCREMENT` never reuses rowids, so re-running
> Phase 1 used to silently orphan every score — measured at 5 of 20 lost from a
> single transcript re-ingest. Identity now lives on the score row, and
> `init_db()` runs an idempotent migration that adds and backfills these
> columns. Read paths use them, not the join (`KNOWN_ISSUES.md` HIGH-2).

> **`model_name` and `prompt_version` are recorded but not constrained.** A
> score series is only valid within one `(model_name, prompt_version)` pair —
> see `SCORING_METHODOLOGY.md` § 4. `check_score_comparability()` reports
> violations, and both the trends CLI and the dashboard surface them, but
> nothing prevents writing them.

## Current data inventory

_Measured 2026-08-23._

- **183 chunk rows** across 11 transcripts: 7 TCS, 4 Infosys (INFY)
- Coverage: Q1 2023 through Q4 2025. **Not contiguous** — INFY has only
  Q1 2023, Q1 2024, Q2 2024, Q4 2025, which breaks the quarter-over-quarter
  assumption in the trend layer (`KNOWN_ISSUES.md` HIGH-3)
- Typical transcript: 16–18 chunks, 8,000–9,100 words
- **24 scores** of a possible 55 (11 × 5): evasiveness 11, sentiment_shift 5,
  complexity_spike 3, overpromising 3, forward_guidance_vagueness 3
- 3 transcripts complete across all 5 dimensions (INFY Q1 2023, INFY Q1 2024,
  TCS Q1 2025)
- **25 scoring runs** in the audit table
- Models present in `scores`: `openai/gpt-oss-120b` (10, the pinned model),
  `llama-3.3-70b-versatile` (9, retired), `openai/gpt-oss-20b` (4),
  `allam-2-7b` (1). The migration onto one model is unfinished — a full sweep
  costs ~5 days of free-tier quota (`KNOWN_ISSUES.md` BLOCKER-4).
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

## Labeled data

`notebooks/reading-notes.md` holds a **completed** human review of all 11
evasiveness-scored transcripts: LLM supporting quotes, a 1–10 rating of the
LLM's accuracy, a written justification, a missed-context note, and a verdict
for each. Mean accuracy rating 4.6/10; verdicts 3 Matches / 3 Partially /
5 Doesn't match.

It is not yet machine-readable, and it records how *wrong* the LLM was rather
than what the correct score is — the "Your Score" column is blank for all 11.
`EVALUATION.md` § 3.1 specifies the `notebooks/labels.csv` format needed before
any error metric can be computed.

`notebooks/evaluation_summary.md` carries score-distribution and
keyword-vs-LLM divergence tables. Note that three of its LLM scores are now
stale relative to the DB, because those transcripts were re-scored under a
different model after the review.

`data/findings/findings.md` is a template for one verified trend-to-stock-move
case study — deliberately still empty; it requires a validated score series.
