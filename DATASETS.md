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
    transcript_id     INTEGER NOT NULL,
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
```

`INSERT OR REPLACE` on `(transcript_id, dimension)` makes re-scoring idempotent.

> **`transcript_id` is not a transcript id.** `transcripts` holds one row per
> *chunk*, so there is no transcript-level identity to reference. Scores are
> filed under the rowid of the transcript's `chunk_index = 0` row. Since
> `store_transcript()` deletes and re-inserts chunks, re-running Phase 1 hands
> out new rowids and silently orphans every score. See `KNOWN_ISSUES.md` HIGH-2
> — this is the schema's most serious defect and should be fixed before the
> next ingest.

> **`model_name` and `prompt_version` are recorded but never enforced.** The
> table currently holds evasiveness scores from three different models. A score
> series is only valid within one `(model_name, prompt_version)` pair — see
> `SCORING_METHODOLOGY.md` § 4.

## Current data inventory

_Measured 2026-08-23._

- **183 chunk rows** across 11 transcripts: 7 TCS, 4 Infosys (INFY)
- Coverage: Q1 2023 through Q4 2025. **Not contiguous** — INFY has only
  Q1 2023, Q1 2024, Q2 2024, Q4 2025, which breaks the quarter-over-quarter
  assumption in the trend layer (`KNOWN_ISSUES.md` HIGH-3)
- Typical transcript: 16–18 chunks, 8,000–9,100 words
- **20 scores** of a possible 55 (11 × 5): evasiveness 11, sentiment_shift 4,
  complexity_spike 2, forward_guidance_vagueness 2, overpromising 1
- **25 scoring runs** in the audit table
- Models present in `scores`: `llama-3.3-70b-versatile`, `openai/gpt-oss-20b`,
  `allam-2-7b`
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
