# PROJECT_CONTEXT.md

## One-sentence summary

EarningsLens is an AI-powered credibility analysis tool that scores Indian
company earnings call transcripts across 5 dimensions to warn retail
investors about red flags before they manifest as stock price crashes.

## Executive summary

EarningsLens ingests PDF earnings call transcripts from Indian companies
(TCS, Infosys, and eventually Wipro, HDFC Bank), extracts and cleans the
text, chunks it into ~600-word paragraph-aware segments, stores it in
SQLite, and scores management credibility via LLM prompting across 5 fixed
dimensions. It's a solo-developer, single-user, locally-run batch pipeline —
not a service.

Status in short (verified 2026-08-23): all four phases have shipped code.
Phase 1 has ingested 11 real transcripts (7 TCS, 4 INFY, Q1 2023–Q4 2025).
Phase 2 has all 5 dimension modules built, but only 20 of a possible 55 scores
exist and they span three different models. Phase 3's functions work while its
CLI crashes on import; Phase 4's dashboard runs but its headline alert is an
artifact of the model mixing.

**Nothing is validated.** The only human review — all 11 evasiveness
transcripts — judged the LLM's score accurate on 3 of them. Treat the current
output as a working pipeline with unproven numbers, not as a credibility
signal. See `KNOWN_ISSUES.md` and `EVALUATION.md`.

## Problem statement

Retail investors in Indian equity markets lack systematic tools to detect
when management is becoming evasive, overpromising, or vague in forward
guidance during earnings calls — language patterns that often precede stock
price declines. EarningsLens quantifies these signals quarter-over-quarter
so a deteriorating trend is visible before it shows up in the price.

## Target users

- **Primary**: Retail investors in Indian markets who want a data-driven
  credibility signal instead of just reading sentiment on their own.
- **Secondary**: The developer, as a demonstrable personal research project;
  also potentially useful to analysts studying corporate governance.
- **Explicitly not building for**: multiple concurrent users, authentication,
  or any multi-tenant use case.

## Non-goals

See `PROJECT_RULES.md` for the enforced list (no LangChain, no vector DB,
no RAG, exactly 5 dimensions, sequential phases).
