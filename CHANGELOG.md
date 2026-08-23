# Changelog

## [0.5.0] - 2026-08-23 — Audit, evaluation, and packaging

The release where the project found out whether it works. It does not, yet, and
that is now measured rather than assumed.

### The headline

Evasiveness scoring was evaluated against 11 human labels and **failed all four
targets**: MAE 1.73, Spearman 0.10, within-2 0.64, directional agreement 0.50.
Spearman 0.10 means the model barely ranks transcripts in the reviewer's order.
See `EVALUATION.md` section 0.

The ground truth for that evaluation existed in the repository the whole time,
recorded in three documents as missing work. A review field labelled "Accuracy"
held the reviewer's own evasiveness scores; confirmed with the reviewer, and
corroborated by the gap-to-verdict correspondence holding across all 11 rows.

### Added

- `src/evaluation/` and `earningslens-evaluate` — MAE, Spearman, within-N, and
  directional agreement, with 24 tests. No new dependency; Spearman comes from
  pandas rather than scipy.
- `src/scoring/prompts.py` — prompts registered by version, with a checksum
  test that fails if a prompt is edited without registering a new version.
- `evasiveness-v2` — targets the four measured failures. Unproven; v1 remains
  the default.
- `earningslens-consistency` — run-to-run score spread. Measured 0 over 5 runs
  on `openai/gpt-oss-120b`, which is what justifies the +/-1.5 trend thresholds.
- `earningslens-check-models` — catches a retired model before it 404s a sweep.
- `pyproject.toml`, six console scripts, pre-commit, `.editorconfig`, and a CI
  matrix over Python 3.11/3.12 that installs the package and smoke-tests the
  entry points.
- `KNOWN_ISSUES.md`, `EVALUATION.md`, `SCORING_METHODOLOGY.md`, `RUNBOOK.md`.

### Fixed

- `scripts/run_trends.py` had never run once — missing `sys.path` prelude, plus
  a `Series.upper()` crash on `--company` behind it.
- Four tests made live API calls, passing in CI only because CI has no API key
  and locally only because an earlier test blanked the key process-wide.
- Re-running Phase 1 silently orphaned every score. Identity moved onto the
  score row; measured at 5 of 20 lost from a single re-ingest.
- `run_phase1.py` had no argparse, so `--help` performed a full re-ingest.
- Quarter-over-quarter deltas ignored calendar gaps — 4 of 7 reported deltas
  were spanning gaps of 2 to 6 quarters.
- `sort_values(key=...)` applied the period key to the company column.
- `prompt_version` was hardcoded, so a revised prompt would write scores
  stamped v1 and defeat the comparability guard.
- Score uniqueness lacked model and prompt version, so scoring with a revised
  prompt would have destroyed the baseline it was meant to be compared against.
- Two divergent implementations of "score all dimensions", one of which
  recorded a model name that had not produced the score.
- Daily token exhaustion was retried as if it were a per-minute limit, and a
  sweep that scored 10 of 55 exited 0.
- 9 type errors that `mypy.ini` was configured to catch but never ran on.

### Known limitations

- No dimension is complete on a single model, so no trend is yet valid. A full
  sweep costs ~1.1M tokens against a 200k/day free tier.
- `llama-3.3-70b-versatile`, which produced most of the original scores, has
  been retired by Groq. Those scores cannot be reproduced.
- n=11 labels, written with the LLM score visible.

---


All notable changes to this project will be documented in this format.
Based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased] — Production Infrastructure Additions

### Added
- `.github/workflows/test.yml` — CI runs `pytest tests/ -v` on every push and pull request
- `config.py` now calls `load_dotenv()` on import — environment variables are loaded at startup
- `config.py` — `LOG_PATH` and `MIN_EXTRACTED_WORDS` constants for logging and validation
- `src/utils/logging.py` — Structured logging module; writes DEBUG+ to `data/earningslens.log`, INFO+ to console
- `src/storage/db.py` — `scoring_runs` table for prompt + model versioning with raw LLM response preservation
- `src/storage/db.py` — `store_scoring_run()` function for inserting scoring metadata
- `scripts/run_phase1.py` — Migrated from `print()` to structured logging via `logger`
- `scripts/run_phase1.py` — PDF extraction validation: rejects extractions below 50 words with a logged warning, continues batch
- `ARCHITECTURE.md` — Full architecture document: data flow diagram, phase map, design decisions, tradeoffs, non-goals
- `scripts/run_evasiveness_test.py` — Now persists every successful LLM scoring response to `scoring_runs` table via `store_scoring_run()` (Fix A, commit 6d76ba2)

### Changed
- `.gitignore` — Added `data/earningslens.log`
- `README.md` — Added CI badge, ARCHITECTURE link, updated project structure and design rules

---

## [Unreleased] — Phase 1: PDF Extraction + Storage (in progress)

### Added
- `config.py` — Centralized paths, constants, filename pattern, chunking target, scoring dimensions
- `src/extraction/pdf_extractor.py` — PyMuPDF-based text extraction with `[PAGE_BREAK]` markers; filename metadata parser (`COMPANY_Q<n>_<year>.pdf`)
- `src/extraction/cleaner.py` — Boilerplate removal (page numbers, confidentiality, disclaimers, URLs); whitespace normalization
- `src/extraction/chunker.py` — Paragraph-aware chunking targeting ~600 words, never splits mid-paragraph
- `src/storage/db.py` — SQLite schema (`transcripts` table with company, quarter, year, chunk_index, chunk_text, word_count, source_file, extracted_at); CRUD (init, store, fetch by company/quarter/year)
- `scripts/run_phase1.py` — Orchestrates full pipeline: discovers PDFs in `data/raw_pdfs/`, extracts → cleans → chunks → stores; writes cleaned text to `data/processed/` for inspection
- `tests/test_extraction.py` — Unit tests for filename parsing, boilerplate cleaning, chunk size compliance
- `requirements.txt` — PyMuPDF, pytest

### Fixed
- Filename parser now raises `ValueError` with clear message for non-conforming PDFs (skip-and-continue in runner)

### Notes
- Phase 1 is **functional but not yet validated end-to-end** — run `python scripts/run_phase1.py` after dropping PDFs in `data/raw_pdfs/`

---

## [Unreleased] — Phase 2: Intelligence Engine (LLM Scoring)

### Added
- `src/scoring/sentiment_shift.py` — LLM-based scoring for tone/attitude shifts across transcript sections
- `src/scoring/complexity_spike.py` — LLM-based scoring for jargon density, nested qualifiers, and language obfuscation
- `src/scoring/overpromising.py` — LLM-based scoring for aggressive guidance, unrealistic targets, and aspirational claims
- `src/scoring/forward_guidance_vagueness.py` — LLM-based scoring for vague forward-looking statements without numbers/timelines
- `src/scoring/__init__.py` — Scoring orchestrator that runs all 5 dimensions and stores results in the `scores` table
- `src/storage/db.py` — `scores` table DDL in `init_db()`, `store_score()` with INSERT OR REPLACE for re-scoring, `get_scores()` with joins
- `tests/test_scoring_dimensions.py` — Unit tests for all 4 new dimensions (LLM mocked), `scores` table CRUD tests, orchestrator import test

### Design decisions
- All 4 new dimensions follow the same module pattern as `evasiveness.py`: system prompt + `_build_prompt()` + `score_<dimension>_llm()` + `score_transcript_<dimension>()`
- Each dimension has a unique system prompt with dimension-specific red-flag patterns (NOT copy-pasted from evasiveness)
- New dimensions use ALL chunks (not Q&A-only) — sentiment, complexity, overpromising, and guidance vagueness appear across the full transcript
- `scores` table uses `UNIQUE(transcript_id, dimension)` with INSERT OR REPLACE to handle re-scoring without duplicates
- The orchestrator (`__init__.py`) is the only file that imports both scoring modules AND `db.py`, maintaining the module boundary rule

---

## Phase 3: Cross-Quarter Comparison (Trend Detection) — shipped `d2f7a99`

### Added
- `src/trends/metrics.py` — `load_scores_from_db`, `compute_qoq_score_change`,
  `compute_rolling_3q_average`, `compute_trend_label`,
  `find_biggest_single_quarter_drop`
- Trend labels: IMPROVING (delta <= -1.5) / STABLE / DETERIORATING (delta >= +1.5)
- `scripts/run_trends.py` — CLI with text and JSON output
- 22 tests in `tests/test_trends.py`

### Known defects at time of writing
- `scripts/run_trends.py` crashes on import (missing `sys.path` prelude)
- QoQ deltas ignore calendar gaps between non-contiguous quarters
- The ±1.5 thresholds are arbitrary — model self-consistency was never measured
- `data/findings/findings.md` remains empty by design (needs validated scores)

---

## Phase 4: Dashboard (Streamlit) — shipped `dc1af41`

### Added
- `src/dashboard/app.py` — company selector plus four tabs: Scores, Trends,
  Alerts, Raw Data
- Per-dimension line charts, QoQ delta bars, rolling 3-quarter averages
- Supporting-quote drill-down per transcript/dimension
- `requirements-dashboard.txt` — streamlit, plotly (optional install)

### Known defects at time of writing
- The Alerts tab's top alert is a model-switch artifact, not a signal
- Four of five trend lines have 1-4 points (20 of 55 scores exist)
- Exportable finding cards were not built
