# PROJECT_STATUS.md

_Last verified against the running code and database on **August 25, 2026**.
Update this file whenever phase status changes — it should always reflect
current reality, not the plan. Every count below was measured, not recalled._

> Companion file: **`KNOWN_ISSUES.md`** lists the verified defects behind the
> qualified statuses here, and which are now fixed. Two blockers remain open: a
> full re-scoring sweep costs ~5 days of free-tier token quota (BLOCKER-4), and
> **the scorer does not discriminate** — it fails all four evaluation targets on
> the cleanest slice available, with a negative rank correlation (BLOCKER-6).
> The second one gates release, and as of 2026-08-25 it does so *mechanically*:
> `run_evaluation.py` exits 3 rather than printing FAIL and exiting 0, and the
> `release-gate` CI job runs on every `v*` tag.
>
> BLOCKER-6 was previously recorded as "not a code defect". Partly wrong: the
> range collapse is caused by averaging per-batch scores (which span 3–8) into
> one number (always 5 or 6). Correcting the aggregation does not fix the
> ranking, so the release verdict is unchanged — see KNOWN_ISSUES.md BLOCKER-6.

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

_Coverage measured 2026-08-25 against `data/earningslens.db`, mid-sweep on the
pinned `openai/gpt-oss-120b`._

| Dimension | Implementation | Scored (any model) | On pinned model | At `-v2` | Human-reviewed |
|---|---|---|---|---|---|
| Evasiveness | ✅ Complete (keyword + LLM) | 11/11 | 7/11 | 7/11 | **11/11** — but see the evaluation below |
| Sentiment shift | ✅ Complete (LLM only) | 4/11 | 2/11 | — | 0/11 |
| Complexity spike | ✅ Complete (LLM only) | 3/11 | 2/11 | — | 0/11 |
| Overpromising | ✅ Complete (LLM only) | 3/11 | 2/11 | — | 0/11 |
| Forward guidance vagueness | ✅ Complete (LLM only) | 3/11 | 2/11 | — | 0/11 |

**24 of 55 dimension-scores exist** (32 rows, since a transcript may hold more
than one prompt variant). Three transcripts — INFY Q1 2023, INFY Q1 2024,
TCS Q1 2025 — are complete across all 5 dimensions.

**No dimension is yet a *complete* series.** The largest clean slice is
`evasiveness-v2` on the pinned model: 7 of 11 transcripts, one model, one
prompt version. That slice is genuinely comparable and can now be selected
directly (`--model` / `--prompt-version`); the remaining 4 transcripts are TCS
Q2 2024, Q3 2024, Q1 2025 and Q4 2025. Without a filter, `run_trends.py` still
says loudly that the table as a whole is mixed rather than quietly
differencing across it.

The `evasiveness-v2` sweep is the work in progress: 7 of 11 transcripts scored.
A single dimension across all 11 costs ~220k tokens against a 200,000/day cap,
so it needs about a full day of quota (`KNOWN_ISSUES.md` BLOCKER-4). The cap is
a rolling 24-hour window, so `scripts/resume_sweep.py` finishes it unattended,
retrying as capacity frees:

```bash
python scripts/resume_sweep.py --dimension evasiveness \
    --prompt-version evasiveness-v2 --wait-minutes 18 --max-hours 20
```

> **Correction (Aug 23), twice over.** This file first recorded "0/11
> human-reviewed"; `notebooks/reading-notes.md` in fact held a completed review
> of all 11 evasiveness transcripts. It was then recorded as an "accuracy
> rating" of the LLM; it is actually the reviewer's **own evasiveness score**,
> confirmed with the reviewer. The project's ground truth existed the whole
> time and was documented as missing. Now exported to `notebooks/labels.csv`.
>
> **Evaluation result:** MAE 1.73, Spearman 0.10, within-2 0.64, directional
> agreement 0.50 — all four targets failed (`EVALUATION.md` § 0).
>
> **Worse on the clean slice (2026-08-25).** Now that one variant can be
> selected, `evasiveness-v2` on the pinned model (n=7) scores MAE 2.43,
> Spearman **−0.73**, within-2 0.43, direction 0.50. The model emits 5 or 6 for
> every transcript while the human labels span 2–9 — it is not discriminating.
> See `KNOWN_ISSUES.md` BLOCKER-6; this, not coverage, is what blocks release.

### Scoring infrastructure

- `scores` table exists in SQLite (per-dimension, per-transcript, queryable)
- `scoring_runs` table stores raw LLM responses for audit trail
- `scripts/run_all_scoring.py` runs all 5 dimensions with `--skip-existing` and `--model` flags
- Shared `_llm_dimension_scorer.py` handles chunk batching (2000-word batches), exponential backoff retry, `<think>` tag stripping
- Daily-quota exhaustion is detected and stops the sweep cleanly (exit 3) rather than burning retries against a 20-minute reset
- `check_score_comparability()` reports any dimension spanning more than one model; the CLI and dashboard both surface it
- `scripts/check_models.py` verifies the pinned model is reachable before scoring
- `scripts/run_self_consistency.py` measures run-to-run spread

### Model

Pinned **`openai/gpt-oss-120b`** on 2026-08-23. The previous
`llama-3.3-70b-versatile` was retired by Groq and 404s, which is why 9 scores
in the DB can never be reproduced.

Self-consistency measured on the pinned model: **spread 0 over 5 runs**
(TCS Q1 2025, evasiveness). The ±1.5 trend thresholds sit above the noise
floor. Cross-model variance on that same transcript is 2 points — model choice
dominates sampling noise entirely.

## Phase 3 — Trend Detection: ✅ Functional, waiting on valid data

The CLI can now be pinned to one `(model, prompt_version)` with `--model` /
`--prompt-version`, and the comparability banner is evaluated against the
selected slice — so a clean slice reports clean instead of being tarred by
rows it is not showing (`KNOWN_ISSUES.md` BLOCKER-5). A dimension with no
scores in the slice is labelled `NO DATA` rather than `STABLE` (MEDIUM-5).

All 4 trend functions implemented and tested (39 tests). The CLI now runs — it
was missing its `sys.path` prelude and had never executed once (BLOCKER-1,
fixed `a1e05ca`).

Correctness fixes since: deltas are gap-aware, so a jump across missing
quarters is blank rather than reported as quarter-over-quarter (4 of 7
previously-reported deltas were spanning gaps); rolling averages require three
consecutive quarters; sorting groups by company instead of collapsing it.

The maths is sound. What it has to read is not yet — see the model note above.

Implemented:
- `compute_qoq_score_change` — quarter-over-quarter deltas per company
- `compute_rolling_3q_average` — rolling 3-quarter averages
- `compute_trend_label` — IMPROVING / STABLE / DETERIORATING labels
- `find_biggest_single_quarter_drop` — largest score increase (worsening) per company/metric
- `load_scores_from_db` — pivots SQLite scores into analysis DataFrame
- `scripts/run_trends.py` — CLI for trend analysis (text and JSON output)

## Phase 4 — Dashboard: ✅ Functional, honest about its data

A sidebar **Score variant** selector pins one `(model, prompt_version)`;
the red banner is computed against whatever is selected. Verified headless,
HTTP 200.

Runs clean (verified headless, HTTP 200). The Scores, Trends, and Alerts tabs
now show a red banner naming any dimension whose scores span multiple models,
so a reader cannot mistake a model-switch artifact for a management signal —
which is exactly what its top alert was.

Coverage is still thin: most trend lines have 1–3 points.

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
- 252 tests across extraction, scoring, trends, evaluation, and integration
- Trend analysis: QoQ deltas, rolling averages, trend labels, drop detection
- Streamlit dashboard with interactive charts and drill-down

## What's explicitly not done yet

- **A complete single-model score sweep.** 24/55 scored, 10 on the pinned
  model. No dimension is yet complete on one model, so no series is valid.
  Blocked on token budget, not on code (`KNOWN_ISSUES.md` BLOCKER-4).
- **A scorer that discriminates.** The evasiveness labels are all filled in
  (`notebooks/labels.csv`), yet the cleanest slice still fails every target —
  Spearman **−0.73** (`KNOWN_ISSUES.md` BLOCKER-6). Until a scoring variant
  ranks transcripts like the reviewer does, the credibility claim stays
  unsupported and the release gate exits 3.
- Prompt quality assessment for the 4 non-evasiveness dimensions
- A verified case study in `data/findings/findings.md`

## Test suite

**252 tests, all passing offline, measured 2026-08-29** (`mypy src/` clean across
24 files). Extraction, scoring, scoring dimensions, trends, evaluation, prompts,
integration, and variant filtering.

Four tests previously reached the live API. They passed in CI only because CI
has no API key, and passed locally only because an earlier test left
`LLM_API_KEY` blank process-wide — each failed when run standalone. All are now
mocked and verified in isolation. CI additionally runs `mypy src/` and
byte-compiles `scripts/`, which had no coverage of any kind before.

See `ROADMAP.md` for what's next and in what order.
