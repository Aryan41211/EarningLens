# KNOWN_ISSUES.md

Verified, reproducible defects found by auditing `main` at `d459f21` on
2026-08-23. Every item was confirmed by running the code or querying
`data/earningslens.db` — nothing here is speculative. Architectural concerns
and history live in `PROJECT_MEMORY.md`; forward plans live in `ROADMAP.md`.

**Status of the audit**

| Issue | Severity | Status |
|---|---|---|
| BLOCKER-1 — trends CLI crashes on import | BLOCKER | ✅ Fixed `a1e05ca` |
| BLOCKER-2 — scores span three models | BLOCKER | ⚠️ Detection added `d21cf63`; **data still contaminated** |
| BLOCKER-3 — configured model has been retired | BLOCKER | ⛔ **Open — blocks all scoring** |
| HIGH-1 — unit tests make live API calls | HIGH | ✅ Fixed `a42fd08`, `20c5842` (4 tests) |
| HIGH-2 — re-ingest orphans every score | HIGH | ✅ Fixed `20c5842` |
| HIGH-3 — QoQ maths ignores calendar gaps | HIGH | ✅ Fixed `f2074f6` |
| MEDIUM-1 — sort key collapses the company column | MEDIUM | ✅ Fixed `f2074f6` |
| MEDIUM-2 — 4 of 5 dimensions have almost no data | MEDIUM | ⛔ Open — needs a scoring sweep, blocked by BLOCKER-3 |
| MEDIUM-3 — human review documented as nonexistent | MEDIUM | ✅ Docs corrected; numeric labels still missing |
| MEDIUM-4 — two divergent score-all implementations | MEDIUM | ✅ Fixed `e1d8a14` |
| LOW batch | LOW | ✅ L-1/2/3/4/5/6 fixed; L-7..L-12 docs corrected |

Descriptions below are kept as originally written, so the reasoning that led
to each fix stays on record.

Severity key:

- **BLOCKER** — a documented feature does not work, or a headline claim is unsupported
- **HIGH** — silently produces wrong output, or destroys data
- **MEDIUM** — correct-by-accident, or misleads the reader
- **LOW** — hygiene / documentation drift

---

## BLOCKER-1 — `scripts/run_trends.py` crashes on import

`PROJECT_STATUS.md` lists Phase 3 as "Functional" and documents this CLI. It
has never run successfully.

```
$ python scripts/run_trends.py
Traceback (most recent call last):
  File "scripts\run_trends.py", line 15, in <module>
    from config import DB_PATH, SCORE_DIMENSIONS
ModuleNotFoundError: No module named 'config'
```

Cause: `run_phase1.py`, `run_all_scoring.py`, and `run_validation_sample.py`
all begin with

```python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
```

`run_trends.py` does not. Python puts the *script's* directory on `sys.path`,
not the working directory, so `config` is unreachable.

Fix: add the same two lines. The underlying trend functions are fine — the
dashboard imports them directly and works.

---

## BLOCKER-2 — Stored scores are not comparable across quarters

The `scores` table mixes three different models under one column, and the
trend layer treats them as a single time series.

| Dimension | Model | Rows |
|---|---|---|
| evasiveness | llama-3.3-70b-versatile | 8 |
| evasiveness | openai/gpt-oss-20b | 2 |
| evasiveness | allam-2-7b | 1 |
| sentiment_shift | openai/gpt-oss-20b | 3 |
| sentiment_shift | llama-3.3-70b-versatile | 1 |
| complexity_spike | openai/gpt-oss-20b | 2 |
| forward_guidance_vagueness | openai/gpt-oss-20b | 2 |
| overpromising | openai/gpt-oss-20b | 1 |

Two consequences, both observable today:

1. **The dashboard's headline alert is a model artifact.** The Alerts tab
   currently reports INFY evasiveness `2 → 6 (+4)`, Q1 2024 → Q2 2024, as the
   biggest single-quarter worsening. The 2 came from `gpt-oss-20b`, the 6 from
   `llama-3.3-70b-versatile`. Nothing about INFY's management changed.
2. **The same transcript scores 4 points apart under two models.** INFY
   Q1 2024 evasiveness is recorded as `6` in `notebooks/reading-notes.md`
   (llama-3.3-70b — the score that was human reviewed) and as `2` in the
   database today (gpt-oss-20b). Same chunks, same prompt version, different
   model.

A quarter-over-quarter delta is only meaningful when model **and** prompt
version are held constant. Nothing in the schema, the runner, or the trend
layer enforces that, even though `scores.model_name` and
`scores.prompt_version` are recorded per row.

Fix direction: make `load_scores_from_db()` refuse to build a series spanning
more than one `(model_name, prompt_version)` per dimension — and pin a model
and re-score all 11 transcripts in one pass. See `SCORING_METHODOLOGY.md`
under Comparability.

---

## BLOCKER-3 — The configured model no longer exists

`.env` pins `LLM_MODEL_NAME=llama-3.3-70b-versatile`. Groq has retired it:

```
openai.NotFoundError: Error code: 404 - The model `llama-3.3-70b-versatile`
does not exist or you do not have access to it.
```

Models actually available on this API key (2026-08-23):

```
allam-2-7b                    openai/gpt-oss-20b
groq/compound                 openai/gpt-oss-120b
groq/compound-mini            openai/gpt-oss-safeguard-20b
qwen/qwen3.6-27b              whisper-large-v3 (speech, not applicable)
```

Consequences:

1. **Any scoring run right now fails.** `run_all_scoring.py` will 404 on every
   call until `LLM_MODEL_NAME` is changed.
2. **8 of the 11 evasiveness scores are unreproducible.** They came from
   llama-3.3-70b-versatile, which can no longer be called. The raw responses
   are preserved in `scores.raw_llm_response`, but the scores cannot be
   regenerated or extended.
3. **The human review in `notebooks/reading-notes.md` reviewed llama-3.3-70b
   output.** Those 11 labels describe the behaviour of a model that no longer
   exists, so they cannot serve as ground truth for whatever model replaces it
   without re-reviewing.

This makes the single-model re-scoring sweep in `ROADMAP.md` step 6 both more
urgent and a genuine decision: the whole series has to be rebuilt on a model
that is still available. `openai/gpt-oss-120b` is the strongest candidate
present; `openai/gpt-oss-20b` already produced 8 of the existing scores.

Lesson worth keeping: a hosted model name is not a stable dependency. Whatever
is pinned next should be recorded in `SCORING_METHODOLOGY.md` with the date it
was pinned, and the retirement risk treated as a matter of when, not if.

---

## HIGH-1 — A unit test makes a live LLM API call

`tests/test_scoring_dimensions.py::test_sentiment_shift_score_key_in_result`
calls `score_transcript_sentiment_shift(...)` with no mock and no env patch.

```
$ python -m pytest tests/ -q
FAILED tests/test_scoring_dimensions.py::test_sentiment_shift_score_key_in_result
  openai.APIConnectionError: Connection error.
1 failed, 69 passed in 8.02s
```

It passes in CI only because CI has no `LLM_API_KEY`, so `score_dimension_llm()`
short-circuits on its "LLM not configured" branch. On any developer machine
with a populated `.env` it attempts a real request — billable,
non-deterministic, and it breaks the suite offline.

So **a green CI badge does not mean the suite passes locally**, and this
violates the standing rule in `CODING_STANDARDS.md` that LLM calls are always
mocked.

Fix: wrap it in the same `@patch.dict("os.environ", ...)` +
`@patch("openai.OpenAI")` pattern already used by the test directly below it.

---

## HIGH-2 — `scores.transcript_id` is a chunk rowid, and re-ingest orphans it

`transcripts` is not a transcript table — it is a *chunks* table, one row per
chunk (183 rows for 11 transcripts). There is no stable transcript identity.

`scripts/run_all_scoring.py::assemble_chunks()` therefore does:

```python
transcript_id = rows[0][0]   # rowid of chunk_index 0
```

Every score is filed under the rowid of that transcript's first chunk
(verified: all 20 scores join to a row with `chunk_index = 0`).

`store_transcript()` does `DELETE ... WHERE company/quarter/year` then
`INSERT`. SQLite `AUTOINCREMENT` never reuses ids, so the re-inserted chunk 0
gets a **new** rowid. Re-running `python scripts/run_phase1.py` — the
documented, supposedly idempotent Phase 1 command — therefore silently orphans
every existing score and scoring run.

Current state: 0 orphans out of 20 scores and 25 runs. One re-ingest destroys
all of them, with no error and no warning; they simply vanish from the `JOIN`
that the trend layer and the dashboard depend on.

Fix direction: either a real `transcripts` table (one row per
company/quarter/year) with a `chunks` child table, or key `scores` on
`(company, quarter, year)` directly.

---

## HIGH-3 — Quarter-over-quarter math ignores calendar gaps

INFY's ingested quarters are Q1 2023, Q1 2024, Q2 2024, Q4 2025 — not
contiguous. `compute_qoq_score_change()` uses `groupby("company").diff()`,
which differences *adjacent rows*, not adjacent quarters. So:

- INFY Q1 2023 → Q1 2024 (four quarters apart) is reported as one QoQ delta
- INFY Q2 2024 → Q4 2025 (six quarters apart) likewise
- `compute_rolling_3q_average()` averages across those same gaps

Nothing in the DataFrame, the CLI output, or the dashboard flags the gap. A
"quarter-over-quarter deterioration" that actually spans 18 months is
indistinguishable from a real one.

Fix direction: compute a period index (`year * 4 + quarter_rank`) and emit
`NaN` for any delta whose period distance is not exactly 1; mark rolling
windows that span a gap.

---

## MEDIUM-1 — `sort_values(key=...)` sorts every column by the period key

Three call sites in `src/trends/metrics.py` do:

```python
df.sort_values(["company", "year", "quarter"], key=lambda s: _quarter_sort_key(df))
```

`key` is applied to **each** `by` column independently, and this lambda ignores
its argument — so the `company` column is also replaced by
`year*10 + quarter_rank`. The sort is effectively by period alone, and
companies interleave:

```
INFY Q1 2023 / TCS Q2 2023 / TCS Q3 2023 / INFY Q1 2024 / TCS Q1 2024 / ...
```

Per-company `diff()` still comes out correct, because period order stays
monotonic *within* each company — this is correct by accident, not by design.
The visible damage is row ordering in the `run_trends.py` tables and the
dashboard's Raw Data tab.

Fix: sort on a real period column instead of abusing `key`.

---

## MEDIUM-2 — 4 of 5 dimensions have almost no data

20 of a possible 55 dimension-scores exist (11 transcripts × 5 dimensions):

| Dimension | Scored | State |
|---|---|---|
| evasiveness | 11 / 11 | full |
| sentiment_shift | 4 / 11 | sparse |
| complexity_spike | 2 / 11 | sparse |
| forward_guidance_vagueness | 2 / 11 | sparse |
| overpromising | 1 / 11 | single point |

Four of five dashboard trend lines are one to four points long. A rolling
3-quarter average needs three consecutive quarters and can never be produced
for `overpromising`. The dashboard renders these as if they were series.

---

## MEDIUM-3 — The human-labeled review set is documented as nonexistent

`PROJECT_STATUS.md` says "0/11 human-reviewed" for every dimension, and
`ROADMAP.md` item 2 is "populate `reading-notes.md` with real human-labeled
examples."

`notebooks/reading-notes.md` already contains a completed human review for
**all 11** evasiveness-scored transcripts: an accuracy rating, a written
justification, missed-context notes, and a verdict for each. It is the most
valuable artifact in the repository and the docs record it as outstanding work.

The one real gap: the "Your Score" column is still blank — the reviewer rated
*how good the LLM's score was*, not what the score should have been. See
`EVALUATION.md`.

---

## MEDIUM-4 — Two divergent implementations of "score all dimensions"

`src/scoring/__init__.py::score_transcript_all()` and the inline loop in
`scripts/run_all_scoring.py::score_dimension()` do the same job differently:
different scorer entry points (`score_transcript_*` vs `score_*_llm`),
different result unwrapping, different model fallback (`"unknown"` vs
`LLM_MODEL_NAME`). Only `score_transcript_all()` is exercised by tests; only
the script is used in production. Neither validates the other.

---

## LOW

| # | Issue |
|---|---|
| L-1 | `check_evasiveness.py` sits in the repo root — an ad-hoc DB query script using `print()`, outside `scripts/`. Violates the layout rule and the no-`print` rule. |
| L-2 | Stray zero-byte file named `0` in the repo root (untracked shell-redirect artifact). |
| L-3 | Empty `.deepeval/` directory, not gitignored — scaffolding from an eval framework that was never set up. |
| L-4 | `requirements-dashboard.txt` header still says the Phase 4 dashboard is "not yet built". |
| L-5 | `mypy.ini` targets Python 3.12; CI runs 3.11 and never invokes mypy at all. |
| L-6 | `_parse_llm_json(raw, score_key)` accepts `score_key` and never uses it. |
| L-7 | Doc drift, all measured: dodge phrases documented as 63, actually **42**; boilerplate patterns documented as 17, actually **13**; tests documented as 103, actually **70**. |
| L-8 | `DATASETS.md` still states per-dimension scores are "not yet in a queryable column"; the `scores` table has existed for weeks. |
| L-9 | `FOLDER_STRUCTURE.md` describes `src/trends/metrics.py` as `NotImplementedError` stubs and `src/dashboard/` as empty. Both shipped in `d2f7a99` / `dc1af41`. |
| L-10 | `TECH_STACK.md` lists Streamlit as "*Planned* — not yet added" and carries a "TODO: confirm pinned versions" that `requirements.txt` answers. |
| L-11 | `CHANGELOG.md` still lists Phases 3 and 4 under `[Unreleased] — Planned, not started`. |
| L-12 | `config.COMPANIES` declares WIPRO and HDFCBANK; neither is ingested and the list is not enforced anywhere. |

---

## Fix order

1. BLOCKER-1 — one line, unblocks the Phase 3 CLI
2. HIGH-1 — one test, makes the suite trustworthy
3. **BLOCKER-3 — pick a model that still exists; nothing can be scored until then**
4. BLOCKER-2 + MEDIUM-2 — pin that model, re-score all 11 × 5 in a single pass
5. HIGH-2 — schema change; do it *before* any further ingest
6. HIGH-3, MEDIUM-1 — trend correctness
7. MEDIUM-3 — then build the harness in `EVALUATION.md`
8. The LOW batch
