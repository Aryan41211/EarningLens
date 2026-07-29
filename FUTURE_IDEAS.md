# FUTURE_IDEAS.md

_Speculative, later-stage, or "nice to have" ideas — not committed to, not
sequenced. Contrast with `ROADMAP.md`, which is the actual near-term plan._

## Coverage expansion

- Ingest Wipro and HDFC Bank transcripts (companies already declared in
  `config.py` but not yet used)
- Expand beyond the 4 hardcoded companies to a configurable watchlist
- Support transcript sources beyond the earnings-call PDF format
  (e.g. investor presentations, annual report MD&A sections)

## Q&A detection robustness

Current Q&A boundary detection uses 4 regex patterns tuned to common Indian
conference-call phrasing ("first question from the line of…"). This is a
known single point of failure for transcripts with different moderator
styles or hosts. A future direction is a more robust/learned boundary
detector rather than pure regex — but this would need to be weighed against
the project's "no vector DB / no RAG" constraint (see `PROJECT_RULES.md`);
any solution should stay a simple classifier, not a retrieval system.

## Scoring quality

- Revisit whether `llama-3.3-70b-versatile` is sufficient quality across all
  5 dimensions, or whether some dimensions need a stronger model
- Consider a second-pass consistency check (re-score a sample, measure
  agreement) once real usage volume exists

## Dashboard ideas beyond Phase 4 baseline

- Alerting (e.g. email/notification when a company's trend crosses a
  threshold)
- Historical backtest view: overlay credibility score trend against actual
  stock price movement for validation, not just the one findings.md case
  study

## Explicitly out of scope for the foreseeable future

- Multi-user support / authentication
- Hosted/cloud deployment
- LangChain/LangGraph, vector DB, or RAG of any kind — these are hard
  constraints, not just deferred ideas (see `PROJECT_RULES.md`)
