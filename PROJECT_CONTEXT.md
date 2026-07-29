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

Status in short: Phase 1 (extraction/storage) is functional and has ingested
11 real transcripts (7 TCS, 4 INFY, Q1 2023–Q4 2025). Phase 2 (scoring) has
1 of 5 dimensions built — evasiveness, via deterministic keyword matching
plus an LLM call to Groq's `llama-3.3-70b-versatile`. Phases 3 (trends) and
4 (dashboard) are stubs.

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
