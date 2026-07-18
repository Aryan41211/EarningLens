# CLAUDE.md — Agent Instructions for EarningLens

## Project
Indian earnings call transcript analysis for red-flag detection across 5 credibility dimensions, quarter over quarter.

## Current Phase (from codebase)
**Phase 1 — PDF extraction + SQLite storage (functional, not validated end-to-end)**
- `src/extraction/`: pdf_extractor → cleaner → chunker
- `src/storage/db.py`: transcripts table, CRUD
- `scripts/run_phase1.py`: orchestrates pipeline
- Run: `python scripts/run_phase1.py` (needs PDFs in `data/raw_pdfs/`)

## Hard Constraints (rules, not suggestions)
1. **No LangGraph, no vector DBs, no RAG** — explicitly out of scope.
2. **No Phase N+1 before Phase N works + tests pass** — sequential only.
3. **No invented metrics** — only report numbers measured on a labeled test set.
4. **Exactly 5 scoring dimensions** — evasiveness, sentiment shift, overpromising, complexity spike, forward guidance vagueness. Do not add without explicit request.

## Key File Locations (don't search, just know)
- `config.py` — all paths, constants, filename regex, chunk target, dimension list
- `data/earningslens.db` — SQLite (gitignored); schema in `src/storage/db.py:13-25`
- `src/extraction/` — Phase 1 pipeline (pdf → clean → chunks)
- `src/storage/` — persistence only
- `src/scoring/` — Phase 2 (empty)
- `src/trends/` — Phase 3 (empty, has `metrics.py` stub)

## Data Directories (gitignored)
- `data/raw_pdfs/` — drop transcripts here (`COMPANY_Q<n>_<year>.pdf`)
- `data/processed/` — cleaned text output for inspection
- Real PDFs never committed.

## Update These When You Finish Meaningful Work
- `CHANGELOG.md` — add entries under the current phase
- `data/findings/findings.md` — fill the template when you have a verified trend→stock-move case

