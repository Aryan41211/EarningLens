# EXPERIMENTS.md

Research/validation work lives in `scripts/_*.py` (underscore-prefixed,
not part of the supported CLI). This doc tracks what each investigated and
what was concluded.

## Chunk windowing — rejected

**Question**: Instead of sending every Q&A chunk to the LLM, could we save
tokens/cost by windowing to just "first 3 + last 2" Q&A chunks?

**Finding**: `scripts/_validate_chunk_window.py` (and the related
`_find_q2_2023_quotes.py`, which cross-referenced specific evidence quotes)
showed empirically that windowing discards LLM-identified evasion evidence
that falls in the middle of the Q&A section.

**Conclusion**: No windowing is applied. Full Q&A chunk set is always sent
to the LLM for scoring. This is now a documented design decision — see
`PROJECT_RULES.md`.

## Token/cost analysis

`scripts/_` token-analysis script(s) estimated per-call token usage and
cost for the evasiveness LLM call. Used to sanity-check that Groq's free
tier is viable for the current transcript volume (11 transcripts).

> TODO: record the actual token/cost numbers here once re-run — not
> preserved in the source notes reviewed.

## Q&A boilerplate analysis

A validation script examined safe-harbor / boilerplate language in prepared
remarks vs. Q&A sections. This is what justified restricting keyword
matching to Q&A chunks only (prepared remarks trigger false positives on
dodge phrases due to standard forward-looking-statement disclaimers).

## DB status checks

`scripts/_db_status.py` — ad-hoc script for inspecting current DB contents
(transcript counts per company/quarter, scoring run counts). Useful during
development for sanity-checking ingestion without opening a SQLite client
directly. Most recently touched script in git history (as of the last
sync — see `PROJECT_MEMORY.md`).

## Open experiments (not yet run)

- No LLM-vs-human-label evaluation has been run yet — blocked on
  `notebooks/reading-notes.md` actually being populated with labels
  (see `ROADMAP.md`)
