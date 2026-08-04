# PROJECT_STATUS.md

_Last synced with repository state ~August 2, 2026. Update this file whenever
phase status changes — it should always reflect current reality, not the plan._

## Phase 1 — Extraction & Storage: ✅ Functional

- PDF → text → clean → chunk → SQLite pipeline works end-to-end
- Validated against 11 real transcripts (7 TCS, 4 INFY)
- Filename metadata parsing, boilerplate stripping, paragraph-aware
  chunking, stale-chunk deduplication all implemented and tested
- Not yet confirmed: a true integration test running the full pipeline
  against real PDFs in CI (current tests use unit-level fixtures)

## Phase 2 — LLM Scoring: 🟡 Partial (1 of 5 validated)

All 5 scoring modules are **implemented** with real LLM prompts and JSON
parsing. However, only Evasiveness has been validated on real transcripts.

### Validation status

| Dimension | Implementation | Production validation |
|---|---|---|
| Evasiveness | ✅ Complete (keyword + LLM) | **11/11 transcripts scored** (7 TCS + 4 INFY). 0/11 human-reviewed. |
| Sentiment shift | ✅ Complete (LLM only) | 1/11 (TCS Q2 2023 test run). 0/11 human-reviewed. |
| Complexity spike | ✅ Complete (LLM only) | 0/11 — zero production validation |
| Overpromising | ✅ Complete (LLM only) | 0/11 — zero production validation |
| Forward guidance vagueness | ✅ Complete (LLM only) | 0/11 — zero production validation |

### What "implemented but not validated" means

- Modules exist in `src/scoring/` with real system prompts, JSON parsing,
  score clamping (1-10), and supporting quote extraction
- Unit tests exist with mocked LLM calls (46 tests pass)
- **No real transcript has been scored** for these 4 dimensions
- Prompt quality, scoring consistency, and edge-case behaviour are unknown
- These should not be treated as production-ready until validated against
  real transcripts with human review

### Scoring infrastructure

- `scores` table exists in SQLite (per-dimension, per-transcript, queryable)
- `scoring_runs` table stores raw LLM responses for audit trail
- `scripts/run_all_scoring.py` runs all 5 dimensions across transcripts
- `scripts/run_evasiveness_test.py` runs evasiveness-only with detailed output

### Current DB state

- **11/11 transcripts scored for evasiveness** (7 TCS + 4 INFY)
- 1 transcript scored for sentiment_shift (TCS Q2 2023 — test run)
- 0 transcripts scored for complexity_spike, overpromising, or forward_guidance_vagueness
- 25 scoring_runs in audit trail
- 0/11 transcripts have been human-reviewed

## Phase 3 — Trend Detection: ⬜ Stub only

`src/trends/metrics.py` has 4 function signatures (QoQ delta, rolling
averages, trend labels, drop detection), all raising `NotImplementedError`.

## Phase 4 — Dashboard: ⬜ Not started

`src/dashboard/__init__.py` is empty. Streamlit not yet added to
dependencies.

## Completed features (cumulative)

- PDF extraction with filename metadata parsing
- Boilerplate stripping (TCS/INFY-specific + generic patterns)
- Paragraph-aware chunking with speaker-label fallback
- SQLite persistence with dedup on re-ingest
- Extraction validation (reject <50-word extracts)
- Structured logging (file DEBUG + console INFO)
- CI via GitHub Actions (pytest on every push/PR)
- All 5 scoring dimension modules implemented with LLM prompts
- Evasiveness keyword matching + LLM scoring, with full audit trail
- Q&A section boundary detection
- `scores` table (per-dimension, per-transcript persistence)
- Manual CLI runner for evasiveness scoring
- Unified scoring runner for all 5 dimensions
- 46+ unit tests across extraction and scoring, LLM calls fully mocked

## What's explicitly not done yet

- Human review of evasiveness scores (0/11 reviewed)
- Production validation of complexity_spike, overpromising, forward_guidance_vagueness (0 transcripts each)
- Prompt quality assessment for non-evasiveness dimensions
- Any trend computation
- Any dashboard
- Evaluation harness against human-labeled data
- End-to-end integration test
- Cleanup of 6 temporary analysis scripts in `scripts/`

See `ROADMAP.md` for what's next and in what order.
