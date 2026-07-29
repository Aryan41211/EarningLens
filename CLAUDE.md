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
- Sequential phases: do not start Phase N+1 work until Phase N is tested and green.
- No `print()` in `src/` — use the structured logger.
- Never commit real API keys. `.env` is gitignored; if a key ever lands in
  git history, treat it as compromised and rotate it.

## Current phase status (see PROJECT_STATUS.md for detail)

| Phase | Status |
|---|---|
| 1 — Extraction & storage | ✅ Functional |
| 2 — LLM scoring | 🟡 1 of 5 dimensions done (evasiveness) |
| 3 — Trend detection | ⬜ Stub only |
| 4 — Dashboard | ⬜ Empty |

## Key files to read before touching code

- `config.py` — single source of truth for paths/constants/regex/dimensions
- `src/scoring/evasiveness.py` — most complex module, reference for the pattern
  the other 4 dimensions should follow
- `src/storage/db.py` — schema + CRUD

## Doc map

| Doc | Covers |
|---|---|
| PROJECT_CONTEXT.md | Problem, users, one-line & executive summary |
| ARCHITECTURE.md | System design, data flow, runtime flow |
| FOLDER_STRUCTURE.md | Directory/file responsibilities |
| TECH_STACK.md | Languages, libraries, LLM/DB/API stack |
| CODING_STANDARDS.md | Style & convention rules |
| DEVELOPMENT_GUIDE.md | Setup, run, test, deploy |
| DATASETS.md | DB schema, current data inventory |
| PROJECT_STATUS.md | Phase-by-phase current state |
| ROADMAP.md | Near-term planned work |
| FUTURE_IDEAS.md | Later-stage / speculative ideas |
| EXPERIMENTS.md | Research scripts & findings |
| PROJECT_RULES.md | Hard constraints / non-goals |
| PROJECT_MEMORY.md | Git history, known issues, tech debt, risks |

## Naming note

> TODO: confirm canonical project name — source notes used "EarningLens" and
> "EarningsLens" interchangeably. This doc set standardizes on **EarningsLens**;
> update if that's wrong.
