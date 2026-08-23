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

## Human review of evasiveness scores — run, result negative

All 11 evasiveness-scored transcripts were read and reviewed by hand
(`notebooks/reading-notes.md`): three LLM supporting quotes each, a 1–10 rating
of the LLM's accuracy, a written justification, and a verdict.

**Result: mean accuracy rating 4.6/10; the reviewer agreed with the LLM's score
on 3 of 11 transcripts (all 4 INFY reviews came back "Doesn't match").**

Failure modes the review surfaced — the model cannot distinguish:

- a refusal with a stated policy reason ("we don't share that externally") from
  a dodge
- a justified guidance band from vague hedging
- a blunt refusal from a courteous one with reasons — tone is invisible to the
  score

Full write-up in `EVALUATION.md` § 1.

## Accidental model comparison — worth converting into a real experiment

The `scores` table ended up holding evasiveness scores from three models. This
was unintentional and it invalidates the current trend data
(`KNOWN_ISSUES.md` BLOCKER-2), but it produced one hard measurement:
**INFY Q1 2024 scored 6 under `llama-3.3-70b-versatile` and 2 under
`openai/gpt-oss-20b`** — identical chunks, identical `evasiveness-v1` prompt.

A 4-point swing on a 10-point scale from model choice alone is larger than any
quarter-over-quarter movement the trend layer has ever reported.

## Open experiments (not yet run)

- **Self-consistency at temperature 0.1** — score one transcript 5 times, same
  model, same prompt, and report the spread. ~10 calls. If the spread nears
  ±2, the ±1.5 trend thresholds sit inside the noise floor and Phase 3's labels
  are meaningless. This should be run before any further scoring work.
  (`EVALUATION.md` § 3.3)
- **Numeric LLM-vs-human error metrics** — blocked not on the review (done) but
  on the reviewer recording their own 1–10 score, which the notes never
  captured. (`EVALUATION.md` § 2)
- **Batch-averaging effect** — the stored score is the mean of ~4–5 independent
  batch judgments. Compare against a single whole-transcript call on a model
  with a large enough context window to see how much averaging flattens the
  distribution (9 of 11 evasiveness scores landed in the 4–6 band).
