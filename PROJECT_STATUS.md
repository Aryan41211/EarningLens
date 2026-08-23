# PROJECT_STATUS.md

_Last verified against the running code and database on **August 23, 2026**.
Update this file whenever phase status changes — it should always reflect
current reality, not the plan. Every count below was measured, not recalled._

> Companion file: **`KNOWN_ISSUES.md`** lists the verified defects behind the
> qualified statuses here. Two blockers are open.

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

| Dimension | Implementation | Scored | Human-reviewed |
|---|---|---|---|
| Evasiveness | ✅ Complete (keyword + LLM) | 11/11 | **11/11** — LLM judged accurate on 3 |
| Sentiment shift | ✅ Complete (LLM only) | 4/11 | 0/11 |
| Complexity spike | ✅ Complete (LLM only) | 2/11 | 0/11 |
| Overpromising | ✅ Complete (LLM only) | 1/11 | 0/11 |
| Forward guidance vagueness | ✅ Complete (LLM only) | 2/11 | 0/11 |

> **Correction (Aug 23):** earlier versions of this file recorded "0/11
> human-reviewed" across the board. `notebooks/reading-notes.md` in fact holds a
> completed review of all 11 evasiveness transcripts — accuracy rating,
> justification, missed-context note, and verdict for each. Mean accuracy
> rating **4.6/10**; verdicts 3 Matches / 3 Partially / 5 Doesn't match. See
> `EVALUATION.md`.

> **The scores in this table are not comparable to each other.** They were
> produced by three different models (`llama-3.3-70b-versatile`,
> `openai/gpt-oss-20b`, `allam-2-7b`) at different times. INFY Q1 2024
> evasiveness moved from 6 to 2 purely from a model switch. See
> `KNOWN_ISSUES.md` BLOCKER-2 before drawing any conclusion from a trend.

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

## Phase 3 — Trend Detection: 🟡 Library works, CLI is broken

All 4 trend functions are implemented and tested (22 tests pass) and the
dashboard imports them successfully. **`scripts/run_trends.py` has never run** —
it is missing the `sys.path` prelude the other scripts have and dies with
`ModuleNotFoundError: No module named 'config'` (KNOWN_ISSUES.md BLOCKER-1).

Two correctness caveats on the functions themselves: QoQ deltas ignore calendar
gaps (INFY's quarters are not contiguous, so some "quarter-over-quarter" deltas
span four to six quarters), and the sort key collapses the company column
(HIGH-3, MEDIUM-1).

Implemented:
- `compute_qoq_score_change` — quarter-over-quarter deltas per company
- `compute_rolling_3q_average` — rolling 3-quarter averages
- `compute_trend_label` — IMPROVING / STABLE / DETERIORATING labels
- `find_biggest_single_quarter_drop` — largest score increase (worsening) per company/metric
- `load_scores_from_db` — pivots SQLite scores into analysis DataFrame
- `scripts/run_trends.py` — CLI for trend analysis (text and JSON output)

## Phase 4 — Dashboard: 🟡 Runs, but shows an artifact as its top alert

The Alerts tab currently reports INFY evasiveness `2 → 6 (+4)` as the biggest
single-quarter worsening. Both numbers came from different models; nothing about
INFY changed. Four of five trend lines have 1–4 points. The UI is sound; the
data underneath it is not yet.

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
- 70 tests across extraction, scoring, trends, and integration
- Trend analysis: QoQ deltas, rolling averages, trend labels, drop detection
- Streamlit dashboard with interactive charts and drill-down

## What's explicitly not done yet

- **A single-model score sweep.** 20/55 scores exist, spread across 3 models.
  Nothing in the DB is currently a valid time series.
- **Numeric human labels.** The review rated the LLM's accuracy but never
  recorded a human 1–10 score, so error cannot be computed (`EVALUATION.md` § 2).
- **Self-consistency measurement.** Nobody has scored the same transcript twice.
  Until that exists, the ±1.5 trend thresholds are unjustified.
- Evaluation harness against human-labeled data
- Prompt quality assessment for the 4 non-evasiveness dimensions
- A verified case study in `data/findings/findings.md`

## Test suite

70 tests: extraction 4, scoring 17, scoring dimensions 25, trends 22,
integration 2. **69 pass, 1 fails locally** —
`test_sentiment_shift_score_key_in_result` makes a real API call and passes in
CI only because CI has no API key (KNOWN_ISSUES.md HIGH-1). A green CI badge
does not currently mean a green local suite.

See `ROADMAP.md` for what's next and in what order.
