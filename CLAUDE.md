# CLAUDE.md — Start Here

> This is the entry point for any agent (or human) working on this project.
> Read this first, then follow links below for depth on any topic.

## What this project is

EarningsLens is a single-user Python tool that scores Indian company earnings
call transcripts for management credibility (evasiveness, sentiment shift,
overpromising, complexity spikes, forward guidance vagueness) so a retail
investor can spot red flags before they show up in the stock price.

Full context: [`PROJECT_CONTEXT.md`](./PROJECT_CONTEXT.md)

## Hard rules (non-negotiable — see PROJECT_RULES.md for full list)

- No LangChain / LangGraph. Direct OpenAI-compatible client calls only.
- No vector DB, no RAG. Scoring is single-prompt, no retrieval.
- Exactly 5 scoring dimensions. Do not add a 6th without an explicit request.
- Sequential phases: do not start Phase N+1 work until Phase N is tested and green
- No `print()` in `src/` — use the structured logger.
- Never commit real API keys. `.env` is gitignored; if a key ever lands in
  git history, treat it as compromised and rotate it.

## Current phase status (see PROJECT_STATUS.md for detail)

| Phase | Status |
|---|---|
| 1 — Extraction & storage | ✅ Functional — 11 transcripts ingested |
| 2 — LLM scoring | 🟡 All 5 modules implemented; 20 of 55 scores exist, none validated |
| 3 — Trend detection | 🟡 Functions work; the CLI (`run_trends.py`) crashes on import |
| 4 — Dashboard | 🟡 Runs, but its headline alert is currently a model artifact |

**Read `KNOWN_ISSUES.md` before trusting any of the above.** Two blockers are
open: the Phase 3 CLI has never run, and the `scores` table mixes three
different LLMs inside one time series, which makes every trend delta suspect.

## Key files to read before touching code

- `config.py` — single source of truth for paths/constants/regex/dimensions.
- `src/scoring/evasiveness.py` — most complex module, reference for the pattern
  the other 4 dimensions follow.
- `src/scoring/_llm_dimension_scorer.py` — shared LLM call: batching, retry,
  JSON parsing, score clamping. All 5 dimensions route through it.
- `src/storage/db.py` — schema + CRUD. Note `transcripts` is really a *chunks*
  table, which is why `scores` carries its own `(company, quarter, year)`
  identity; `init_db()` migrates and backfills it.
- `src/trends/metrics.py` — trend maths. Deltas are gap-aware and
  `check_score_comparability()` refuses to treat mixed-model scores as a series.
- `src/evaluation/metrics.py` — the metrics that decide whether any of this
  works. Read `EVALUATION.md` before changing a threshold.

## Doc map

| Doc | Covers |
|---|---|
| **KNOWN_ISSUES.md** | **Verified, reproducible defects — read this first** |
| **SCORING_METHODOLOGY.md** | **What a score means and when two scores may be compared** |
| **EVALUATION.md** | **How to prove the scores work; existing human-review evidence** |
| **RUNBOOK.md** | **Exact commands, health checks, troubleshooting** |
| KNOWN_ISSUES status table | Which defects are fixed and which remain |
| PROJECT_CONTEXT.md | Problem, users, one-line & executive summary |
| ARCHITECTURE.md | System design, data flow, runtime flow |
| FOLDER_STRUCTURE.md | Directory/file responsibilities |
| TECH_STACK.md | Languages, libraries, LLM/DB/API stack |
| CODING_STANDARDS.md | Style & convention rules |
| DEVELOPMENT_GUIDE.md | Setup, test, contribute (running the pipeline → RUNBOOK.md) |
| DATASETS.md | DB schema, current data inventory |
| PROJECT_STATUS.md | Phase-by-phase current state |
| ROADMAP.md | Near-term planned work |
| FUTURE_IDEAS.md | Later-stage / speculative ideas |
| EXPERIMENTS.md | Research scripts & findings |
| PROJECT_RULES.md | Hard constraints / non-goals |
| PROJECT_MEMORY.md | Git history, tech debt, risks |

## Doc hygiene rule

These docs have drifted from the code before — phases were documented as
"functional" while their CLI could not import, and a completed human review was
recorded as "0/11 reviewed". When you change behaviour, update the doc in the
same commit, and prefer a measured number ("42 dodge phrases") over a
remembered one.

## Naming note

The repository directory and git remote are `EarningLens`; every document and
all user-facing text use **EarningsLens**. Both refer to the same project.
