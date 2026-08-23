# ARCHITECTURE.md

## Overview

A strictly sequential 4-phase pipeline. Each phase is a separate module tree
that only talks to the next stage through SQLite — modules never import
across phase boundaries.

```
data/raw_pdfs/
    │  (COMPANY_Q<n>_<year>.pdf)
    ▼
src/extraction/pdf_extractor.py      → raw text, [PAGE_BREAK]-joined pages
    │                                    + filename metadata parse
    ▼  (reject if < 50 words)
src/utils/text_cleaning.py           → boilerplate stripped (headers,
    │                                    footers, page numbers, disclaimers)
    ▼  (also written to data/processed/ for inspection)
src/extraction/chunker.py            → ~600-word paragraph-aware chunks
    ▼
src/storage/db.py                    → SQLite `transcripts` table
    ▼  (Phase 2 — manual trigger)
src/scoring/evasiveness.py           → keyword matching + LLM (Q&A chunks only)
src/scoring/sentiment_shift.py       → LLM (all chunks)
src/scoring/complexity_spike.py      → LLM (all chunks)
src/scoring/overpromising.py         → LLM (all chunks)
src/scoring/forward_guidance_vagueness.py → LLM (all chunks)
    │   all five route through src/scoring/_llm_dimension_scorer.py
    ▼   (batching, retry, JSON parse, 1-10 clamp)
src/storage/db.py                    → SQLite `scores` + `scoring_runs`
    ▼  (Phase 3)
src/trends/metrics.py                → QoQ deltas, rolling averages,
                                         trend labels, drop detection
    ▼  (Phase 4)
src/dashboard/app.py                 → Streamlit UI
```

Phases 3 and 4 are implemented as of `d2f7a99` / `dc1af41`. Neither is
trustworthy yet: the Phase 3 CLI crashes on import and the score series feeding
both mixes three models. See `KNOWN_ISSUES.md`.

## Key architectural principles

- **Module isolation by responsibility**: extraction never touches storage
  internals; storage never imports PyMuPDF; scoring never imports extraction.
- **Scripts orchestrate, modules implement**: everything in `scripts/` is
  composition only — no business logic lives there.
- **`config.py` is the single source of truth** for paths, constants, regex,
  scoring dimensions, and LLM settings. No module hardcodes a path.
- **Auditability over convenience**: every LLM call's raw JSON response is
  persisted — in `scoring_runs` and again on each `scores` row, alongside the
  model name and prompt version. This is the only reason the three-model
  contamination in the current data was diagnosable after the fact.

## Runtime flow — Phase 1 (`scripts/run_phase1.py`)

1. Import `config.py` → `load_dotenv()` loads `.env`.
2. `setup_logger()` — file handler at DEBUG, console handler at INFO.
3. `init_db()` — creates `transcripts` / `scoring_runs` tables if absent.
4. Discover `*.pdf` in `data/raw_pdfs/`, sorted alphabetically.
5. Per PDF: parse filename metadata → extract text → validate (≥50 words) →
   clean → write to `data/processed/` → chunk → `store_transcript()`
   (deletes stale chunks for that company/quarter/year before inserting).
6. Close DB connection.

## Runtime flow — Phase 2 (`scripts/run_evasiveness_test.py [COMPANY]`)

1. Load all quarters for the company from SQLite.
2. `get_chunks()` → all chunks for a transcript.
3. `find_qa_start_index()` — regex-detects where Q&A begins (variants of
   "first question from the line of…").
4. `score_evasiveness_keywords()` — deterministic dodge-phrase matching,
   restricted to Q&A chunks only (prepared remarks are skipped to avoid
   safe-harbor boilerplate false positives).
5. `score_evasiveness_llm()` — sends Q&A chunks to Groq's
   `llama-3.3-70b-versatile` via an OpenAI-compatible client, temperature
   0.1, requests a 1–10 score plus supporting quotes as JSON.
6. `store_scoring_run()` persists the run (model, prompt version, raw
   response) to `scoring_runs`.

## Runtime flow — Phases 3 & 4

`load_scores_from_db()` pivots the `scores` table into one row per
`(company, quarter, year)` with a column per dimension, then the four trend
functions derive `<dim>_delta`, `<dim>_ma3`, and `<dim>_trend` columns from it.
`scripts/run_trends.py` and `src/dashboard/app.py` are two consumers of the same
functions — the dashboard does not go through the CLI, which is why it works
while the CLI does not.

## Design decisions

See `PROJECT_RULES.md` for the full enumerated list of hard constraints and
their rationale (SQLite over Postgres, no vector DB, no LangChain, Q&A-only
keyword scoring, no chunk windowing, etc.).
