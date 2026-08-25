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
| 2 — LLM scoring | 🟡 All 5 modules implemented; 32 score rows, evaluation FAILS |
| 3 — Trend detection | ✅ Functional — CLI runs, gap-aware, variant-selectable |
| 4 — Dashboard | ✅ Functional — variant selector; honest about thin coverage |

**Read `KNOWN_ISSUES.md` before trusting any of the above.** The pipeline works
end to end. The open blockers are about the *result*, not the code:

- **BLOCKER-6 — the scorer does not discriminate.** On the cleanest slice
  available (evasiveness-v2, pinned model, n=7) it fails all four evaluation
  targets, with Spearman **−0.73** while human labels span 2–9.
  **Do not ship the credibility claim.** Note the cause was re-measured on
  2026-08-25: the *stored* scores are all 5 or 6, but the model's per-batch
  scores span 3–8 — the range is destroyed by averaging batches in
  `score_dimension_llm()`, not by the model. Restoring it does not restore the
  ranking (no aggregator turns Spearman positive), so the verdict is unchanged.
- **BLOCKER-4 — a full sweep costs ~5 days of free-tier quota**, so coverage
  stays thin (evasiveness-v2 is 7/11; the other four dimensions are 2–3/11).

**`evasiveness-v3` is built but unmeasured** (2026-08-25). It scores each
analyst exchange separately instead of averaging word-count windows, keeps
every per-exchange score, and costs the same as a v2 sweep. Nothing has been
scored with it and `evasiveness-v1` is still the registry default — it makes no
claim until a sweep runs. RUNBOOK § 9. Note also **HIGH-10**: the human labels
score three quotes while the LLM scores the whole call, so the two were never
commensurable — some of the −0.73 is that, not the model.

**The gate is mechanical now.** `python scripts/run_evaluation.py --dimension
evasiveness --against reviewed` exits **3** while the targets are missed, and
CI runs it on every `v*` tag. Deploy the dashboard as a tool to look at data if
you like — `docker build -t earningslens .`, RUNBOOK § 10 — but a non-zero gate
means the scores are not a validated credibility measure.

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
| **RUNBOOK.md** | **Exact commands, health checks, troubleshooting, v3 sweep (§ 9), deployment (§ 10)** |
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
