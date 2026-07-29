# PROJECT_STATUS.md

_Last synced from project understanding reports dated ~July 26, 2026. Update
this file whenever phase status changes — it should always reflect current
reality, not the plan._

## Phase 1 — Extraction & Storage: ✅ Functional

- PDF → text → clean → chunk → SQLite pipeline works end-to-end
- Validated against 11 real transcripts (7 TCS, 4 INFY)
- Filename metadata parsing, boilerplate stripping, paragraph-aware
  chunking, stale-chunk deduplication all implemented and tested
- Not yet confirmed: a true integration test running the full pipeline
  against real PDFs in CI (current tests use unit-level fixtures)

## Phase 2 — LLM Scoring: 🟡 Partial (1 of 5 dimensions)

- **Evasiveness** — implemented and manually tested across all TCS/INFY
  quarters. Deterministic keyword matching (Q&A chunks only) + LLM scoring
  via Groq `llama-3.3-70b-versatile`, persisted to `scoring_runs`.
- **Sentiment shift** — not started
- **Overpromising** — not started
- **Complexity spike** — not started (Flesch readability formula planned)
- **Forward guidance vagueness** — not started

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
- Evasiveness keyword matching + LLM scoring, with full audit trail
- Q&A section boundary detection
- Manual CLI runner for evasiveness scoring
- 15+ unit tests across extraction and scoring, LLM calls fully mocked

## What's explicitly not done yet

- 4 of 5 scoring dimensions
- Dedicated `scores` table (scores currently only live inside JSON blobs)
- Any trend computation
- Any dashboard
- Evaluation harness against human-labeled data
- End-to-end integration test

See `ROADMAP.md` for what's next and in what order.
