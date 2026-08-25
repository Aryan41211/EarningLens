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
| BLOCKER-3 — configured model has been retired | BLOCKER | ✅ Fixed `e89ca03` — pinned `openai/gpt-oss-120b` |
| BLOCKER-4 — a full sweep exceeds the free tier's daily token budget | BLOCKER | ⚠️ Handled in code `dc14c30`; **sweep still incomplete** |
| HIGH-1 — unit tests make live API calls | HIGH | ✅ Fixed `a42fd08`, `20c5842` (4 tests) |
| HIGH-2 — re-ingest orphans every score | HIGH | ✅ Fixed `20c5842` |
| HIGH-3 — QoQ maths ignores calendar gaps | HIGH | ✅ Fixed `f2074f6` |
| MEDIUM-1 — sort key collapses the company column | MEDIUM | ✅ Fixed `f2074f6` |
| MEDIUM-2 — 4 of 5 dimensions have almost no data | MEDIUM | ⛔ Open — needs a scoring sweep, blocked by BLOCKER-3 |
| MEDIUM-3 — human review documented as nonexistent | MEDIUM | ✅ Fixed `1ddea00` — labels existed all along, now in `labels.csv` |
| MEDIUM-4 — two divergent score-all implementations | MEDIUM | ✅ Fixed `e1d8a14` |
| LOW batch | LOW | ✅ L-1/2/3/4/5/6 fixed; L-7..L-12 docs corrected |
| NEW: `prompt_version` was hardcoded, defeating the comparability guard | HIGH | ✅ Fixed `7aa6a68` — registry + checksum test |
| HIGH-4 — a truncated batch was dropped silently, biasing the average | HIGH | ✅ Fixed 2026-08-24 — salvage + `max_tokens` 1600 |
| HIGH-5 — `--skip-scored` ignored `prompt_version`, so a v2 sweep skipped v1-scored transcripts | HIGH | ✅ Fixed 2026-08-24 — matched on `(dimension, prompt_version)` |
| BLOCKER-5 — nothing could *read* a single variant, so BLOCKER-2 had no remedy | BLOCKER | ✅ Fixed 2026-08-25 — `--model` / `--prompt-version` on the trends CLI, variant selector in the dashboard |
| HIGH-6 — rolling averages crashed on a dimension with no scores | HIGH | ✅ Fixed 2026-08-25 — dimension columns coerced to float64 |
| HIGH-7 — `run_evaluation.py --prompt-version` bypassed the guard and crashed with a raw `MergeError` | HIGH | ✅ Fixed 2026-08-25 — guard sees the filter; `--model` now applied |
| MEDIUM-5 — an unscored dimension was labelled `STABLE` | MEDIUM | ✅ Fixed 2026-08-25 — now `NO DATA` |
| L-13 — `pyproject` declared MIT with no LICENSE file; dashboard caption hardcoded v0.1 | LOW | ✅ Fixed 2026-08-25 |
| HIGH-8 — a failing evaluation exited 0, so no release step could gate on it | HIGH | ✅ Fixed 2026-08-25 — exit code 3 + `gate()`, tested |
| HIGH-9 — the dashboard's Raw Data tab ignored the variant selector | HIGH | ✅ Fixed 2026-08-25 — quotes filtered, regression-tested |
| MEDIUM-6 — no deployable artifact and no way to run the gate in CI | MEDIUM | ✅ Fixed 2026-08-25 — Dockerfile, `.streamlit/config.toml`, `image` + `release-gate` CI jobs |
| HIGH-10 — the human labels score 3 quotes, the LLM scores the whole call; the two were compared as if commensurable | HIGH | ⛔ Open — needs new labels; documented 2026-08-25 |
| **BLOCKER-6 — the scorer does not discriminate: on the cleanest slice it fails all four targets, Spearman −0.73** | **BLOCKER** | ⛔ **Open — cause partly corrected 2026-08-25; `evasiveness-v3` built but unmeasured** |

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

## BLOCKER-4 — A full scoring sweep does not fit in the free tier's daily budget

Discovered by running one. Groq's free tier caps **tokens per day at 200,000**,
separately from the per-minute limit the retry logic was built for:

```
429 - Rate limit reached for model `openai/gpt-oss-120b` ... on tokens per day
(TPD): Limit 200000, Used 199839, Requested 3462. Please try again in 23m46s.
```

### The arithmetic

| Quantity | Value |
|---|---|
| Words per transcript | ~8,500 |
| Batches per dimension (at `_BATCH_TARGET_WORDS = 2000`) | 4–5 |
| Tokens per dimension-score | ~20,000 |
| Dimension-scores for a full sweep (11 × 5) | 55 |
| **Total tokens for one full sweep** | **~1.1M** |
| **Free-tier daily budget** | **200,000** |

**A complete sweep needs roughly five days of free-tier quota.** This is a
structural constraint, not a tuning problem: the cost is dominated by the
transcript text itself, which is sent once per dimension. Larger batches save
only the repeated system prompt (~10%).

The first sweep completed 10 of 55 dimension-scores before exhausting the
budget — and the self-consistency experiment run beforehand had already spent
roughly a third of that day's allowance.

### What this does to the plan

`ROADMAP.md` step 6 assumed a full sweep was a single 20–40 minute operation.
It is not. The options, none free:

1. **Spread across ~5 days.** Free, slow, and the series stays incomplete
   meanwhile. `--skip-existing` resumes without redoing finished transcripts.
2. **Upgrade to Groq's Dev Tier.** Fastest path to a complete, comparable
   series.
3. **Score fewer dimensions.** Evasiveness alone is 11 × 20k = 220k tokens —
   still over one day, but close. It is also the only dimension with human
   review, so it is the one where a complete series is worth most.
4. **Score fewer transcripts.** A contiguous 4-quarter run of TCS across all 5
   dimensions is 400k tokens and would actually demonstrate the trend feature,
   which the current sparse coverage cannot.

Option 3 or 4 buys a *defensible* result soonest. Option 1 eventually buys the
complete one.

### Handled in code

`dc14c30` added `DailyQuotaExhausted`: the scorer now distinguishes a daily cap
from a per-minute limit, stops the sweep instead of burning retries against a
20-minute reset, keeps everything already written, and exits 3 with a count of
what remains. Previously this exact situation exited **0** while logging
"2 fully succeeded, 9 had failures".

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

## HIGH-4 — A batch cut off by the token limit was dropped from the average

Found on 2026-08-24, on the first batch of the first transcript of the
`evasiveness-v2` sweep.

```
WARNING  |   LLM returned invalid JSON (evasiveness): {"evasiveness_score": 7,
"supporting_quotes": ["Nilanjan Roy: \"And one more reason is that the top-end
has come down is also largely also due to the delay in mega deals signing and
the transition tim
```

`max_tokens` was **800**, which does not fit `evasiveness-v2`'s three verbatim
quotes. The response stopped mid-quote, `json.loads` failed, and
`_score_single_batch()` returned `None` — which `score_dimension_llm()` then
excluded from `all_scores` without recording that it had done so. The score
became the mean of the batches that happened to parse.

Two things made this worse than a lost batch:

1. **The dropout is not random.** Truncation happens precisely when the model
   emits long quotes, which is not independent of what is being scored. So the
   bias has a direction, and it lands hardest on the transcripts with the most
   quotable evasive material.
2. **The score was there all along.** The model emits `evasiveness_score`
   *before* `supporting_quotes`, so the truncated response above carried a
   perfectly good `7`. The code threw it away because the quote list was
   incomplete.

Measured: 1 of 6 batches truncated in the interrupted sweep.

This would have silently corrupted the v1-vs-v2 comparison that the sweep
exists to produce — v1's shorter output rarely truncates at 800 tokens, so v2
alone would have been scored on a shrunken and biased sample of its batches.

### Fixed

- `_salvage_truncated_json()` recovers the score, plus whichever quotes closed
  before the cutoff, instead of discarding the batch.
- `max_tokens` 800 → 1600. Output tokens are a rounding error against the ~20k
  input tokens each dimension-score already spends on transcript text.
- `finish_reason` is now read, so a length cutoff logs differently from a
  malformed reply.
- `score_dimension_llm()` returns `batches_used` / `batches_total` and warns
  when they differ, so a partial aggregate can never again look complete.

The one v2 score already in the database (INFY Q1 2023) came from the pre-fix
path, 4 of 5 batches. Recomputing with the salvaged batch yields the same
value, 6 — so nothing stored changes, and the raw responses are retained.

---

## HIGH-5 — `--skip-scored` skipped on the model alone, ignoring the prompt version

Found on 2026-08-24 while resuming the `evasiveness-v2` sweep.

`--skip-scored` is the documented way to finish a sweep that exceeds the daily
token budget: re-run it and it picks up where it stopped. Its filter,
`get_scored_on_model()`, matched on `(dimension, model_name)` and never looked
at `prompt_version`.

So during a **v2** sweep it treated a transcript already scored at
`evasiveness-v1` on the pinned model as finished. Observed directly:

```
$ ... --dimension evasiveness --prompt-version evasiveness-v2 --skip-scored --dry-run
Dimension-scores to produce: 8      # should have been 10
```

INFY Q1 2024 and INFY Q2 2024 were stepped over — the two transcripts that had
v1 scores on `openai/gpt-oss-120b` but no v2 score at all.

The damage is quiet and permanent. A skip is not an error, so the sweep would
have reported success while leaving holes in exactly the series it was building,
and the resulting v2 "series" would have been silently short — with the missing
transcripts being a biased subset, since they are the ones scored earliest.

Fix: match on the `(dimension, prompt_version)` pairs the run would actually
write, defaulting to each dimension's registered version when none is requested.
Covered by `tests/test_resume_skip.py` (5 tests), including the inverse case —
a v1 row *does* mean "done" when the run would write v1.

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

**Resolved, and worse than first described.** The per-transcript field was
labelled "Accuracy" and was read — by this document included — as a rating of
the LLM. It is the reviewer's own evasiveness score, confirmed with them and
corroborated by the gap-to-verdict correspondence holding across all 11 rows.

So the project's ground truth existed from the start and was recorded as
missing work in three separate documents. The field is relabelled and exported
to `notebooks/labels.csv`; the evaluation now runs (`EVALUATION.md` § 0).

Worth keeping as a lesson: an ambiguous field label cost this project its own
evidence, and the audit that found the other issues initially propagated the
misreading rather than catching it.

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

## BLOCKER-5 — No reader could select a single variant

Added 2026-08-25.

BLOCKER-2 established that a delta is meaningless unless model and prompt
version are held constant, and `d21cf63` added detection. But detection without
selection is a dead end: `load_scores_from_db()` grew `model` /
`prompt_version` parameters and **no caller passed them**.

- `scripts/run_trends.py` had no such flags at all.
- `src/dashboard/app.py` called `load_scores_from_db(conn)` bare.
- `check_score_comparability(conn)` always inspected the whole table, so even a
  caller that *had* filtered would still be told its clean slice was
  contaminated.

The practical effect: the project could name its own contamination but never
show a reader the uncontaminated series sitting inside the same table. The
`evasiveness-v2` sweep on the pinned model was 7 transcripts of perfectly
comparable data, and every entry point rendered it mixed with three other
models under a banner saying not to trust it.

### Fixed

- `check_score_comparability(conn, model=None, prompt_version=None)` — checks
  the slice being displayed, so a clean slice reports clean.
- `run_trends.py --model NAME --prompt-version VERSION`, echoed in the header.
- Dashboard sidebar "Score variant" selector, listing every
  `(model, prompt_version)` present with its row count.

Verified: `run_trends.py --model openai/gpt-oss-120b --prompt-version
evasiveness-v2` emits no contamination banner and 7 comparable transcripts.

---

## HIGH-6 — Rolling averages crashed on an unscored dimension

Found 2026-08-25, immediately after BLOCKER-5's filter made empty columns real.

`load_scores_from_db()` created any missing dimension column with `pd.NA`,
which gives the column **object** dtype. `.rolling()` refuses object dtype:

```
TypeError: cannot handle this type -> object
  ... in compute_rolling_3q_average
    .transform(lambda x: x.rolling(window=3, min_periods=3).mean())
```

It stayed hidden only because every unfiltered load happened to contain at
least one score for all 5 dimensions. Narrowing to one variant leaves four
columns entirely empty and the CLI died halfway through its output — after
printing the QoQ table, so it looked like a partial success.

Fix: create missing columns as `float("nan")` and `pd.to_numeric` every
dimension column. Object dtype was wrong regardless of who reads it.

---

## HIGH-7 — `--prompt-version` bypassed the comparability guard, then crashed

Found 2026-08-25.

`run_evaluation.py` cleared its guard whenever `--prompt-version` was passed:

```python
if args.prompt_version:
    # An explicit variant was requested, so the mix is already resolved.
    blocked = set()
```

A prompt version is **not** a variant. `evasiveness-v1` exists under three
models, so the filter left duplicate `(company, quarter, year, dimension)` rows
— and the guard that would have explained this had just been switched off. The
run ended in an unhandled traceback:

```
$ python scripts/run_evaluation.py --dimension evasiveness --prompt-version evasiveness-v1
pandas.errors.MergeError: Merge keys are not unique in left dataset;
not a one-to-one merge
```

Compounding it, `--model` was documented as a filter, accepted by argparse, and
**never passed to `load_scores()`** on the main path — it took effect only
under `--compare`.

Fix: `--model` is applied; `check_score_comparability` receives the same
filter, so it reports on the requested slice instead of being disabled. The
command above now exits 2 with the three offending models named.

---

## MEDIUM-5 — An unscored dimension was labelled STABLE

`compute_trend_label()` fell through to `STABLE` for any NaN delta, collapsing
three different situations into one reassuring word: a genuinely small change,
a delta unavailable across a calendar gap, and **a dimension that was never
scored at all**.

With four of five dimensions near-empty (MEDIUM-2), the trend column read
`STABLE` across the board — a claim about management, made from no measurement.
Same failure mode as BLOCKER-2's headline alert: an artifact wearing the
costume of a signal.

Fix: a row whose dimension score is missing is labelled `NO DATA`. A *scored*
row whose delta is NaN (first quarter, or a gap) stays `STABLE`, which is the
existing tested behaviour and a separate judgement call.

---

## HIGH-8 — A failing evaluation exited 0

Found 2026-08-25.

`run_evaluation.py` printed `FAIL` against all four targets and exited `0`:

```
$ python scripts/run_evaluation.py --dimension evasiveness \
      --model openai/gpt-oss-120b --prompt-version evasiveness-v2
  MAE                       2.43  FAIL
  Spearman                 -0.73  FAIL
  Within 2 points           0.43  FAIL
  Directional agreement     0.50  FAIL
$ echo $?
0
```

EVALUATION.md § 3.2 defines the targets, KNOWN_ISSUES.md says not to ship
without them, and nothing in the repository could act on either statement. The
one check the whole project rests on was advisory text.

Fix: `gate()` / `gate_dimension()` in `src/evaluation/metrics.py` turn the four
metrics into a verdict, and the script exits `3` when any target is missed.
An **unmeasured** metric — a score column with no variance, or no adjacent
quarters to difference — is `UNMEASURED`, not `PASS`: treating an absent result
as a satisfied one is how an unvalidated claim reaches a user. Evaluating zero
dimensions is likewise never a pass. `--no-gate` restores the old behaviour for
exploratory runs.

The gate also runs without a database via `--against reviewed`, which reads
`notebooks/labels.csv` alone, so CI can enforce it on a version tag.

---

## HIGH-9 — The dashboard's Raw Data tab ignored the variant selector

Found 2026-08-25, in the fix for BLOCKER-5.

BLOCKER-5 added a sidebar variant selector and threaded it through the scores
table, the charts and the comparability banner — but not through the
Supporting Quotes query at the bottom of the Raw Data tab, which still filtered
on `company` alone.

A reader who selected `evasiveness-v2` therefore saw v2 scores in every chart
and, underneath them, the quotes **every** model had produced for the same
quarters — the same transcript listed several times over with no indication of
which row belonged to the score above it. That is BLOCKER-2's failure mode
surviving inside the fix for BLOCKER-2.

Fix: the same `model` / `prompt_version` filter is applied to the quote query.
`tests/test_dashboard.py` covers it, and the dashboard now has test coverage at
all — it previously had none, which is why this shipped.

---

## BLOCKER-6 — The scorer does not discriminate (OPEN)

Found 2026-08-25, once BLOCKER-5 made a clean evaluation possible for the first
time. This is the finding that actually gates release.

Evaluated on the cleanest slice that exists — `evasiveness-v2` on the pinned
`openai/gpt-oss-120b`, 7 transcripts, one model, one prompt version:

| Metric | Target | Measured | |
|---|---|---|---|
| MAE | ≤ 1.5 | **2.43** | FAIL |
| Spearman | ≥ 0.6 | **−0.73** | FAIL |
| Within 2 points | ≥ 0.7 | **0.43** | FAIL |
| Directional agreement | ≥ 0.7 | **0.50** | FAIL |

The Spearman is *negative*: on this sample the model ranks transcripts close to
the reverse of the reviewer's order. The paired data shows why:

| Company | Quarter | LLM (v2) | Human |
|---|---|---|---|
| INFY | Q1 2023 | 6 | 3 |
| INFY | Q1 2024 | 6 | 2 |
| INFY | Q2 2024 | 5 | 9 |
| INFY | Q4 2025 | 6 | 3 |
| TCS | Q2 2023 | 5 | 4 |
| TCS | Q3 2023 | 6 | 5 |
| TCS | Q1 2024 | 5 | 6 |

**The model emits 5 or 6 for everything.** Its output spans 1 point; the
reviewer's spans 7 (2–9). It is not mis-calibrated, which rescaling could fix
— it is not discriminating at all, and the residual ordering is noise that
happens to point the wrong way. The one call the reviewer flagged hardest
(INFY Q2 2024, human 9) is the *lowest* score the model gave.

Corroboration from the other slices, same labels:

- `--against reviewed` (n=11, the llama-3.3-70b scores the human actually saw):
  MAE 1.73, Spearman 0.10, within-2 0.64, direction 0.50. All four fail.
- `evasiveness-v1` on the pinned model (n=3): MAE 4.00, direction 0.00.

So this is not an artifact of v2, of the pinned model, or of the small sample
alone — no slice yet measured comes near a passing score, and the failure is
consistently one of *range*.

### Correction, 2026-08-25: part of it *is* a code defect

This section previously opened "Nothing in this repository is wrong." That was
measurably false, and the sentence was written without checking the one place
the evidence was sitting: `scores.raw_llm_response` keeps every per-batch
response, so the scores that went into each stored average can be read back.

A transcript's Q&A is split into ~2000-word batches, each batch is asked to
judge the call as a whole, and the batch verdicts are **averaged**. Those
verdicts are not flat — they use most of the scale:

| Transcript | Per-batch scores | Stored |
|---|---|---|
| INFY Q1 2023 | 7, 5, 6, 4, 7 | 6 |
| INFY Q1 2024 | 3, 7, 7, 4, 8 | 6 |
| INFY Q2 2024 | 8, 3, 7, 3 | 5 |
| INFY Q4 2025 | 7, 8, 6, 3 | 6 |
| TCS Q2 2023 | 4, 8, 3 | 5 |
| TCS Q3 2023 | 5, 6, 7 | 6 |
| TCS Q1 2024 | 3, 7, 5, 4 | 5 |

The model's batch judgements span **3 to 8**. Every stored score is 5 or 6. The
range does not collapse in the model — it collapses in `score_dimension_llm()`,
where a mean of three-to-five noisy whole-call judgements has a narrower
distribution than the judgements themselves, by construction. The pipeline also
contradicts its own prompt: `evasiveness-v2` says "WEIGH THE WHOLE Q&A, NOT THE
WORST MOMENT", and no call ever sees the whole Q&A.

So "the model emits 5 or 6 for everything" was the wrong reading. The model
emits 3 through 8; the aggregation emits 5 or 6.

### Why the blocker stays open anyway

Restoring the range does **not** restore the ranking. Every alternative
aggregator, recomputed from the same stored batch scores against the same 7
labels:

| Aggregator | Range | Spearman | MAE |
|---|---|---|---|
| mean (current) | 1.0 | −0.73 | 2.43 |
| mean, unrounded | 1.2 | −0.46 | 2.37 |
| median | 3.0 | −0.70 | 2.57 |
| max | 1.0 | −0.22 | 3.29 |
| 75th percentile | 1.8 | −0.20 | 2.71 |
| top-2 mean | 1.5 | −0.34 | 2.71 |

All still negative. The batch verdicts vary, but they do not vary *with* the
reviewer's judgement, so no operator over them recovers the order. The headline
claim remains unsupported, and the release verdict is unchanged: **do not ship
it.**

The aggregation was therefore left in place and instrumented rather than
swapped — changing it would invalidate the stored series under
`SCORING_METHODOLOGY.md` § 7 and buy nothing measurable. `score_dimension_llm()`
now returns `batch_scores` and logs a warning whenever the batch spread is ≥ 4,
so the discarded range is visible at scoring time.

Completing the sweep (BLOCKER-4) will not change this either. It will raise n
from 7 to 11 and make the number more certain — most likely more certainly a
failure. Shipping a credibility signal that is anti-correlated with human
judgement on its only labelled dimension would be worse than shipping nothing.

### What would actually address it

Roughly in order of expected value:

1. **Stop asking a fragment to judge the whole.** This is now the top item, not
   the third. Either score the full Q&A in one call (6k–10k tokens, which is
   above the 8000 TPM free-tier ceiling that forced batching in the first
   place), or score per question and aggregate deliberately rather than by
   accident.
2. **Force the range.** The prompt asks for 1–10 and the pipeline yields 5–6.
   Anchored rubrics with worked examples at 2, 5 and 9, or forced ranking of
   transcripts against each other, attack the collapse directly.
3. **Score the Q&A section only.** Already done for evasiveness
   (`find_qa_start_index()`); still outstanding for the other four dimensions,
   which are handed the whole transcript.
4. **Re-check against a held-out label set.** The 11 labels informed v2's design
   (EVALUATION.md § 1.5), so they can no longer certify it. New labels are
   needed before any variant can be called validated out-of-sample.
5. **Only then** spend the ~5 days of quota on a full sweep.

Until one of these moves Spearman decisively positive, the honest status of the
headline claim is *unsupported*.

### A second measurement problem, found 2026-08-25: the labels and the scores
### are not measuring the same thing

Reading `notebooks/reading-notes.md` closely while building v3 turned up
something that changes how every evaluation number so far should be read.

The reviewer did not read 11 transcripts. For each one they were shown **the
three supporting quotes the v1 model had surfaced** — its three most evasive
picks — and scored from those. EVALUATION.md § 1.1 says as much ("For each:
three LLM supporting quotes, the reviewer's own 1–10 evasiveness score"), but
the consequence was never drawn:

- The **human label** is a *worst-three-moments* judgement.
- The **LLM score** is a *whole-call average* over ~13 exchanges.

These are different quantities, and the human one is conditioned on which
quotes v1 happened to choose. A whole-call mean will always compress toward the
middle relative to a worst-three statistic, so part of the measured failure is
an artefact of comparing them at all — before any question of prompt quality.

The clearest case is INFY Q2 2024, the reviewer's 9/10. All three quotes are
flat non-disclosures with no reason attached ("We do not really break up that
cost further"). Against 13 exchanges, most of which were answered normally,
*no* whole-call average could return a 9. Against those three quotes, 9 is a
defensible read.

Two consequences:

1. **Some of the −0.73 is measurement mismatch, not model failure.** How much
   is unknown and cannot be established from these labels.
2. **It constrains what a fix may look like.** An aggregate that is
   commensurable with the labels has to be a worst-few statistic. That is why
   `evasiveness-v3` defaults to `worst3_mean` — and why a good score from it on
   *these* labels would still not be out-of-sample evidence.

The clean resolution is new labels gathered against a stated unit: either the
reviewer scores whole transcripts, or the scorer is evaluated per exchange
against per-exchange labels. Until then, treat every evaluation number on this
dimension as carrying an unquantified validity error on top of its small n.

---

## evasiveness-v3 — per-exchange scoring (built 2026-08-25, unmeasured)

Registered, tested and reachable; **no transcript has been scored with it**, so
it makes no claim yet. Built to attack the two problems above at once.

**What changed.** The unit of judgement. v1/v2 hand the model a ~2000-word
window and ask it to judge the whole call, then average the windows. v3 splits
the Q&A into individual analyst exchanges (`split_qa_into_exchanges()`, on the
moderator's turn — 10–18 per transcript, median ~400 words, retaining ~99% of
Q&A words) and asks for **one score per exchange**. Aggregation into a
transcript score then happens in code, where it is named and testable, instead
of implicitly in the transport layer.

**Cost is unchanged.** Measured on INFY Q2 2024: 15 exchanges pack into 4
requests, exactly what v2 used, over the same input text. The output budget is
sized per request (860/720/1000/720 tokens) against v2's flat 1600. A full
11-transcript sweep is still ~220k tokens, ~1.1 days of free-tier budget.

**Every per-exchange score is stored** in `scores.raw_llm_response` as JSON.
That is the deliberate answer to BLOCKER-4: the expensive part is paid once,
and `scripts/compare_aggregators.py` (`earningslens-aggregators`) re-runs every
aggregator over the stored scores and re-measures against the labels **without
making a single LLM call**.

**Aggregators available:** `worst3_mean` (default), `worst2_mean`, `max`,
`mean`, `median`, `dodge_rate`. The default is a worst-few statistic for the
two reasons given above — it matches the product's claim (red flags, not
averages) and it is the only family commensurable with how the labels were
produced.

**What would falsify it.** Score the 11 transcripts, then run
`earningslens-aggregators`. If the `spread` column is near zero for every
aggregator, the model is genuinely not discriminating and the problem was never
the aggregation. If spread is healthy but Spearman stays negative, the rubric
is wrong. Both outcomes are informative and cost one sweep.

**What it is not.** It is not validated, and it cannot be validated on the
existing 11 labels: those labels informed v2's design (EVALUATION.md § 1.5) and
were produced by a different measurement unit than v3 uses. The default
aggregator was chosen partly to match them, which is selection on the test set.
`evasiveness-v1` remains the registry default and the release gate still fails.

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
