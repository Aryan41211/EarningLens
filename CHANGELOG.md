# Changelog

## [Unreleased] - 2026-08-29 — Second audit round: scorer hardening, script flags, dependency fixes

### Fixed

- **`--year` in `run_evasiveness_test.py` was silently dead** — the loop
  rebound `year` before it was read, so the flag had no effect. The loop now
  filters on the requested year (H1).
- **`413` was treated as a rate limit** in `_llm_dimension_scorer.py`. A 413 is
  a request-shape/payload error, not a quota error, and will not clear after a
  wait — burning the whole retry budget and mislabelling the cause. It now
  raises immediately (M3).
- **The retry-after parser only matched "try again in …"** — Groq also emits
  "retry in …". The regex now matches both phrasings (L5).
- **An empty transcript could reach the LLM as a zero-chunk batch** and be
  answered by a guess. `_batch_chunks([])` now returns `[]` (L6).
- **numpy was an undeclared direct dependency** (HIGH-11's lesson). It is now
  declared in `pyproject.toml`, `requirements.txt`, and the `Dockerfile`, and
  the duplicate inline import in `src/evaluation/metrics.py` was removed (M1).
- **`run_validation_sample.py` hardcoded the five dimension names** instead of
  iterating `DIMENSION_MODULES` — a diverging copy of the registry (L2).
- **`store_score` docstring said "INSERT OR REPLACE"** but the query is an
  `ON CONFLICT ... DO UPDATE` upsert; the docstring now describes the real
  behaviour (L1).

### Added

- `run_evasiveness_test.py` now honours `--prompt-version` and `--aggregator`,
  so a v3 per-exchange sweep is selectable from the CLI (M2).
- `tests/test_llm_scorer_helpers.py` — unit tests pinning batching and the
  retry-after parser.
- Test count is now **250** (measured).

## [Unreleased] - 2026-08-29 — First real CI run, scipy fix, Docker Hub release path

### Fixed

- **scipy was an undeclared dependency** (`KNOWN_ISSUES.md` HIGH-11). Spearman
  came from `pandas.Series.corr(method="spearman")`, which needs scipy, while
  the module claimed no scipy and none was declared — so the test suite and the
  release gate crashed in a clean CI environment. Spearman is now computed in
  pure pandas/numpy (Pearson of average ranks, identical to
  `scipy.stats.spearmanr`), pinned by two new tie-behaviour tests.
- `README.md`/`RUNBOOK.md`/`PROJECT_STATUS.md` carried remembered, drifting
  figures — test counts (116/189/173) and a "labels still blank" claim that the
  data had answered. Corrected to the measured 243 tests and the real
  BLOCKER-6 blocker.

### Added

- **`image-publish` CI job** — builds and pushes `aryankondekar/earningslens`
  to Docker Hub as `{version}` and `latest` on a `v*` tag (or on demand), hard-
  gated on the `release-gate` job so a pre-evaluation image is never published.
- **ROADMAP Step 6** — a command-by-command plan to close BLOCKER-6 (v3 sweep →
  `earningslens-aggregators` → v1 baseline → rubric/label work → out-of-sample),
  with the free-tier token cost of each decision.

## [Unreleased] - 2026-08-24 — Truncated responses no longer vanish

### Fixed

- **A batch whose response was cut off was dropped silently from the average.**
  `max_tokens` was 800, which is not enough for `evasiveness-v2`'s three
  verbatim quotes; the response stopped mid-quote, failed `json.loads`, and the
  batch was excluded — shrinking the divisor with no error, only a `WARNING`.
  The dropout is not random: truncation happens when the model emits long
  quotes, so the batches most likely to be discarded are not independent of
  what is being scored. Measured at 1 of 6 batches in the 2026-08-24 sweep.
- The score survives truncation even when the quote list does not, because the
  model emits it first. `_salvage_truncated_json()` now recovers the score plus
  whichever quotes closed before the cutoff, instead of discarding the batch.
- `max_tokens` raised 800 → 1600. Output tokens are a rounding error next to
  the ~20k input tokens each dimension-score already spends on transcript text.
- `finish_reason` was never read, so a length cutoff was indistinguishable from
  a malformed reply. It is now checked and logged distinctly.
- A partial aggregate is no longer silent: `score_dimension_llm()` returns
  `batches_used` / `batches_total` and warns when they differ.

- **`--skip-scored` ignored `prompt_version`.** The documented way to resume a
  sweep matched on `(dimension, model)` only, so a v2 sweep treated
  v1-scored transcripts as finished and stepped over INFY Q1 2024 and Q2 2024 —
  planning 8 transcripts where 10 remained. A skip is not an error, so the run
  would have reported success while leaving permanent holes in the series it
  was building. Now matched on the `(dimension, prompt_version)` pairs the run
  would actually write.

### Added

- `scripts/resume_sweep.py` and `earningslens-resume` — drives a sweep to
  completion across the rolling token budget, retrying on exit 3 rather than
  needing a human to re-run it for a day.
- `run_evaluation.py --compare` — two prompt versions side by side on the same
  labels. Implements `EVALUATION.md` § 1.5 option 3 and enforces its conditions:
  an unsuppressible IN-SAMPLE banner, the model held constant (or the v1 column
  would be a three-model mix and the delta would measure the model switch), and
  the comparison restricted to transcripts scored under every version, since
  11-vs-3 side by side compares transcripts rather than prompts.
- `--model` on the evaluator, to choose which model is held constant.

### Notes

- The one `evasiveness-v2` score in the database (INFY Q1 2023) was produced by
  the pre-fix path from 4 of 5 batches. Recomputing with the salvaged batch
  gives the same value, 6, so no stored score changes.
- The v2 sweep reached 1 of 11 transcripts before the free-tier daily token
  budget was exhausted, and stopped cleanly with exit 3. Roadmap step 22 is
  still open.
- § 1.5 decision recorded: option 3 is implemented because it is the only one
  available without the reviewer; option 1 — fresh labels written before any
  LLM score is seen — remains the clean answer and the recommended next step.
- Even once v2 covers all 11, a like-for-like v1-vs-v2 covers only the 3
  transcripts v1 has on the pinned model. A clean 11-vs-11 prompt comparison
  needs v1 re-scored on the pinned model across all 11: another ~220k tokens.

---

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
