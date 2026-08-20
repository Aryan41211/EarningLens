# PROJECT_STATUS.md

_Last synced with repository state ~August 21, 2026. Update this file whenever
phase status changes — it should always reflect current reality, not the plan._

## Phase 1 — Extraction & Storage: ✅ Functional

- PDF → text → clean → chunk → SQLite pipeline works end-to-end
- Validated against 11 real transcripts (7 TCS, 4 INFY)
- Filename metadata parsing, boilerplate stripping, paragraph-aware
  chunking, stale-chunk deduplication all implemented and tested

## Phase 2 — LLM Scoring: 🟡 Partial (1 of 5 validated on real data)

All 5 scoring modules are **implemented** with real LLM prompts and JSON
parsing. Shared LLM scorer with chunk batching and retry logic.
Only Evasiveness has been validated on real transcripts.

### Validation status

| Dimension | Implementation | Production validation |
|---|---|---|
| Evasiveness | ✅ Complete (keyword + LLM) | **11/11 transcripts scored**. 0/11 human-reviewed. |
| Sentiment shift | ✅ Complete (LLM only) | 2/11 scored (TCS Q1 2025, TCS Q2 2023). 0/11 human-reviewed. |
| Complexity spike | ✅ Complete (LLM only) | 1/11 scored (TCS Q1 2025). 0/11 human-reviewed. |
| Overpromising | ✅ Complete (LLM only) | 1/11 scored (TCS Q1 2025). 0/11 human-reviewed. |
| Forward guidance vagueness | ✅ Complete (LLM only) | 2/11 scored (TCS Q1 2025, INFY Q1 2023). 0/11 human-reviewed. |

### Scoring infrastructure

- `scores` table exists in SQLite (per-dimension, per-transcript, queryable)
- `scoring_runs` table stores raw LLM responses for audit trail
- `scripts/run_all_scoring.py` runs all 5 dimensions with `--skip-existing` and `--model` flags
- Shared `_llm_dimension_scorer.py` handles chunk batching (2000-word batches), exponential backoff retry, `<think>` tag stripping
- `openai/gpt-oss-20b` model validated as working with Groq free tier (8000 TPM)

### Current DB state

- **11/11 transcripts scored for evasiveness** (7 TCS + 4 INFY)
- **20 total scores** across all dimensions
- TCS Q1 2025 has all 5 dimensions scored
- Other transcripts have 1-3 dimensions scored
- Full scoring of all 11 transcripts × 5 dimensions requires additional LLM runs

## Phase 3 — Trend Detection: ✅ Functional

All 4 trend functions implemented and tested (22 tests pass):
- `compute_qoq_score_change` — quarter-over-quarter deltas per company
- `compute_rolling_3q_average` — rolling 3-quarter averages
- `compute_trend_label` — IMPROVING / STABLE / DETERIORATING labels
- `find_biggest_single_quarter_drop` — largest score increase (worsening) per company/metric
- `load_scores_from_db` — pivots SQLite scores into analysis DataFrame
- `scripts/run_trends.py` — CLI for trend analysis (text and JSON output)

## Phase 4 — Dashboard: ✅ Functional

Streamlit dashboard (`src/dashboard/app.py`) with:
- Company selector sidebar
- **Scores tab**: line chart of all dimensions, latest trend labels
- **Trends tab**: QoQ delta bar chart, rolling 3-quarter average line chart
- **Alerts tab**: biggest single-quarter worsening events, cross-company trend summary
- **Raw Data tab**: full data table, supporting quotes drill-down
- Run with: `streamlit run src/dashboard/app.py`
- Dashboard dependencies in `requirements-dashboard.txt` (streamlit, plotly)

## Completed features (cumulative)

- PDF extraction with filename metadata parsing
- Boilerplate stripping (TCS/INFY-specific + generic patterns)
- Paragraph-aware chunking with speaker-label fallback
- SQLite persistence with dedup on re-ingest
- Extraction validation (reject <50-word extracts)
- Structured logging (file DEBUG + console INFO)
- CI via GitHub Actions (pytest on every push/PR)
- All 5 scoring dimension modules with LLM prompts
- Shared LLM scorer with chunk batching, retry, thinking-tag stripping
- Evasiveness keyword matching + LLM scoring, with full audit trail
- Q&A section boundary detection
- `scores` table (per-dimension, per-transcript persistence)
- Unified scoring runner for all 5 dimensions with `--model` and `--skip-existing`
- 69+ unit tests across extraction, scoring, and trends
- Trend analysis: QoQ deltas, rolling averages, trend labels, drop detection
- Streamlit dashboard with interactive charts and drill-down

## What's explicitly not done yet

- Human review of scores (0 transcripts reviewed)
- Complete scoring of all 11 transcripts × 5 dimensions (currently 20/55 scores)
- Prompt quality assessment for non-evasiveness dimensions
- Evaluation harness against human-labeled data
- End-to-end integration test for the full pipeline

See `ROADMAP.md` for what's next and in what order.
