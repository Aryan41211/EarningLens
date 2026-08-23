# EarningsLens

AI system that reads Indian company earnings call transcripts and scores
management credibility across 5 dimensions, quarter over quarter, to warn
retail investors before red flags turn into stock price crashes.

[![Tests](https://github.com/Aryan41211/EarningLens/actions/workflows/test.yml/badge.svg)](https://github.com/Aryan41211/EarningLens/actions/workflows/test.yml)

## Status

All four phases have shipped code; none is finished. 11 transcripts are
ingested, 20 of a possible 55 dimension-scores exist, and **no score has been
validated** — the one human review that exists judged the LLM accurate on 3 of
11 transcripts.

| Phase | State |
|---|---|
| 1 — Extraction & storage | Functional |
| 2 — LLM scoring | 5 modules implemented, 20/55 scores, unvalidated |
| 3 — Trend detection | Functions work; the CLI crashes on import |
| 4 — Dashboard | Runs; top alert is currently a model artifact |

Start with **[KNOWN_ISSUES.md](KNOWN_ISSUES.md)** — two blockers are open.

[RUNBOOK](RUNBOOK.md) · [EVALUATION](EVALUATION.md) · [SCORING_METHODOLOGY](SCORING_METHODOLOGY.md) · [ARCHITECTURE](ARCHITECTURE.md) · [CHANGELOG](CHANGELOG.md)

## Project Structure

```
earningslens/
├── .github/workflows/     # CI: GitHub Actions runs tests on every push
├── ARCHITECTURE.md        # End-to-end data flow, design decisions, tradeoffs
├── config.py              # All paths and constants - single source of truth
├── data/
│   ├── raw_pdfs/          # Drop downloaded transcript PDFs here
│   ├── earningslens.db    # SQLite DB (created automatically, gitignored)
│   └── earningslens.log   # Structured log file (DEBUG+; gitignored)
├── src/
│   ├── extraction/        # PDF -> text -> clean -> chunks (Phase 1)
│   ├── storage/           # SQLite schema + CRUD (Phase 1)
│   ├── scoring/           # LLM scoring engine, 5 dimensions (Phase 2)
│   ├── trends/            # QoQ deltas, rolling averages, labels (Phase 3)
│   ├── evaluation/        # LLM-vs-human metrics (MAE, Spearman, direction)
│   ├── dashboard/         # Streamlit app (Phase 4)
│   └── utils/             # Logging, shared text cleaning helpers
├── scripts/
│   ├── run_phase1.py           # Extraction -> storage
│   ├── run_all_scoring.py      # All 5 dimensions against every transcript
│   ├── run_evasiveness_test.py # Manual evasiveness runner, one company
│   ├── run_validation_sample.py# One transcript, all 5 dimensions, for review
│   ├── run_trends.py           # Trend analysis CLI
│   ├── run_evaluation.py       # LLM scores vs human labels
│   ├── run_self_consistency.py # Run-to-run score spread
│   ├── check_models.py         # Is the pinned model still reachable?
│   └── check_db_status.py      # Ad-hoc DB inspection
└── tests/                      # 116 tests
    ├── test_extraction.py          # Filename parsing, cleaning, chunking
    ├── test_scoring.py             # Keyword matching, Q&A detection, mocked LLM
    ├── test_scoring_dimensions.py  # 4 LLM-only dimensions, DB CRUD
    ├── test_trends.py              # QoQ, rolling averages, labels, drops
    ├── test_evaluation.py          # MAE, Spearman, within-N, direction
    └── test_integration.py         # End-to-end scoring with a mocked LLM
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in LLM API key when you get to Phase 2
```

## Running the pipeline

```bash
python scripts/run_phase1.py        # 1. PDFs in data/raw_pdfs/ -> chunks in SQLite
python scripts/run_all_scoring.py   # 2. score all 5 dimensions (--dry-run first)
python scripts/run_trends.py        # 3. trend analysis
streamlit run src/dashboard/app.py  # 4. dashboard
python scripts/run_evaluation.py    # 5. is any of it actually accurate?
```

Scoring is not cheap: ~20k tokens per dimension-score, against a 200k/day free
tier. `--dry-run` prints the estimate. Scope with `--dimension NAME` and resume
with `--skip-scored`; see [RUNBOOK.md](RUNBOOK.md).

PDFs must be named `COMPANY_Q<n>_<year>.pdf` (e.g. `TCS_Q1_2025.pdf`) — the
regex has no fallback for other names.

Full operational detail, cost estimates, health checks, and troubleshooting:
**[RUNBOOK.md](RUNBOOK.md)**.

## Design rules

- Each module in `src/` does one job. Extraction never touches SQLite.
  Storage never touches PyMuPDF.
- `config.py` is the only place paths/constants live.
- No LangChain, LangGraph, or vector DBs — this project doesn't need them.
- `scripts/` only orchestrates; real logic always lives in `src/`.
- Structured logging via Python's `logging` module. Always use `logger`, never `print`.

## Notes & Findings

- [notebooks/reading-notes.md](notebooks/reading-notes.md) — Completed human
  review of all 11 evasiveness-scored transcripts. The reviewer rated the LLM's
  accuracy at **4.6/10 on average** and agreed with its score on 3 of 11.
  This is the project's current headline result; see
  [EVALUATION.md](EVALUATION.md).
- [notebooks/evaluation_summary.md](notebooks/evaluation_summary.md) — Score
  distribution and keyword-vs-LLM divergence tables.
- [data/findings/findings.md](data/findings/findings.md) — The single
  demonstrable case where trend detection would have flagged a company before a
  stock move. Deliberately empty: filling it requires a validated score series,
  which does not exist yet.