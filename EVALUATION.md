# EVALUATION.md

Whether EarningsLens actually works. Every claim it makes — "management is
getting more evasive", "this trend preceded a stock move" — is worth exactly as
much as the scores behind it.

**As of 2026-08-23 those scores have been measured, and they do not hold up.**
The result is in § 0. `EXPERIMENTS.md` records the supporting research.

---

## 0. The result

**Evasiveness scoring, measured against 11 human labels, fails all four
targets.**

```
evasiveness  (n=11)          measured   target
  MAE                            1.73   <= 1.50   FAIL
  Spearman                       0.10   >= 0.60   FAIL
  Within 2 points                0.64   >= 0.70   FAIL
  Directional agreement          0.50   >= 0.70   FAIL   (4 comparisons)
```

Reproduce with `python scripts/run_evaluation.py --dimension evasiveness
--against reviewed`. Scores are the ones the reviewer actually saw
(`llama-3.3-70b-versatile`), so this is a clean single-model comparison.

**Spearman 0.10 is the finding that matters.** It means the model has close to
zero ability to rank transcripts by evasiveness — it is not "a bit off", it is
not ordering them. And directional agreement of 0.50 across 4 adjacent-quarter
comparisons is a coin flip on the exact claim the product makes: *this quarter
is worse than last quarter*.

Caveats, stated so this is not over-read:

- n = 11, and only 4 adjacent-quarter pairs. This is evidence, not proof.
- The labels were written with the LLM's score visible, which anchors
  judgement — recorded as `confidence: medium` in `labels.csv`.
- It measures `llama-3.3-70b-versatile`, which Groq has since retired. The
  currently pinned `openai/gpt-oss-120b` is unmeasured; on the one transcript
  scored by both, it disagreed by 2 points.

**What this does not mean:** that the idea is wrong. It means *this prompt, on
this model, does not reproduce human judgement*. The failure modes in § 1.2 are
specific and addressable — the model treats a reasoned refusal as a dodge. That
is a prompt problem before it is a concept problem.

**What it does mean:** no credibility claim, dashboard reading, or case study
should be presented as meaningful until a revised prompt clears these targets.

---

## 1. What evidence exists today

### 1.1 The human review set

`notebooks/reading-notes.md` contains a completed human review of all 11
evasiveness-scored transcripts. For each: three LLM supporting quotes, **the
reviewer's own 1–10 evasiveness score**, a written justification, a "key missed
context" note, and a verdict.

> **Correction (2026-08-23).** That field was originally labelled "Accuracy",
> and earlier versions of this document read it as *how accurate the LLM was* —
> reporting a "mean accuracy rating of 4.6/10". That was wrong. The field holds
> the reviewer's own evasiveness score, confirmed with the reviewer and
> corroborated by the data: the gap between LLM score and this field predicts
> the recorded verdict perfectly across all 11 rows (gap 0 → "Matches" 3/3,
> gap 1 → "Partially" 3/3, gap ≥2 → "Doesn't match" 5/5). The field has been
> relabelled and exported to `notebooks/labels.csv`.
>
> The consequence is large: the project's ground truth existed all along, and
> was documented as missing.

| Transcript | LLM score | Human score | Gap | Verdict |
|---|---|---|---|---|
| INFY Q1 2023 | 7 | 3 | 4 | Doesn't match |
| INFY Q1 2024 | 6 | 2 | 4 | Doesn't match |
| INFY Q2 2024 | 6 | 9 | 3 | Doesn't match |
| INFY Q4 2025 | 6 | 3 | 3 | Doesn't match |
| TCS Q2 2023 | 6 | 4 | 2 | Doesn't match |
| TCS Q3 2023 | 6 | 5 | 1 | Partially |
| TCS Q1 2024 | 7 | 6 | 1 | Partially |
| TCS Q2 2024 | 4 | 4 | 0 | Matches |
| TCS Q3 2024 | 6 | 5 | 1 | Partially |
| TCS Q1 2025 | 6 | 6 | 0 | Matches |
| TCS Q4 2025 | 4 | 4 | 0 | Matches |

The LLM matches the human exactly on **3 of 11**, is within one point on 6 of
11, and every INFY transcript is off by 3 or more.

Two patterns worth noting. The LLM's scores cluster tightly in 4–7 (a
consequence of averaging across batches — see `SCORING_METHODOLOGY.md` § 3)
while the human's range 2–9. And the errors are not one-directional: the model
scores INFY Q1 2024 four points *too high* and INFY Q2 2024 three points *too
low*. It is not miscalibrated by a constant offset, which is what Spearman 0.10
reflects — there is no consistent relationship to correct for.

### 1.2 What the reviewer found the LLM gets wrong

Recurring themes, quoted from the review notes:

- **Refusal ≠ evasion.** "They have given a valid reason i.e. they don't share
  that info externally." The model scores a declined answer as a dodge even
  when management states a coherent policy reason.
- **Justified hedging read as hedging.** On INFY's guidance band: "Good
  justification, but somewhat vague." The model penalises the range itself
  rather than the reasoning behind it.
- **Boundary-setting read as deflection.** "This one feels the most like
  management drawing a boundary. Reasonable policy, but it limits transparency."
  A defensible disclosure policy and an evasive non-answer score the same.
- **Tone is invisible to the score.** The reviewer repeatedly separates *rude,
  flat refusal* from *professional refusal with reasons* — a distinction the
  1–10 scale cannot express and the prompt never asks for.

### 1.3 Why the existing labels are already partly stale

Three of the 11 reviewed scores no longer match the database, because those
transcripts were re-scored under a different model after the review:

| Transcript | Score reviewed | Score in DB now | Model that produced the DB score |
|---|---|---|---|
| INFY Q1 2023 | 7 | 8 | openai/gpt-oss-20b |
| INFY Q1 2024 | 6 | **2** | openai/gpt-oss-20b |
| TCS Q1 2025 | 6 | 7 | allam-2-7b |

The INFY Q1 2024 swing — 6 to 2 on identical chunks and an identical prompt
version — is the single clearest measurement in the repository of how much of
a "score" is model choice rather than signal. See `KNOWN_ISSUES.md` BLOCKER-2.

---

## 1.5 A trap to avoid when revising the prompt

`evasiveness-v2` was written to address the failure modes in § 1.2. It is
tempting to re-run the evaluation on the same 11 labels and report the new
number as the result.

**That number would be contaminated.** Those 11 transcripts are the only
labelled data, and they informed the prompt's design — measuring on them is
measuring on the training set. A v2 that scores better may simply have absorbed
the eleven answers.

v2 was deliberately written from the *stated principles* in the review ("a
refusal with a reason is not a dodge", "tone is not evasiveness") rather than
from the eleven scores, which limits the leakage but does not remove it.

Honest options, in order of strength:

1. **Label more transcripts and hold them out.** The clean answer. Label before
   seeing any LLM score.
2. **Split the existing 11.** Use a handful to inspect failure modes and keep
   the rest untouched for measurement. With n=11 both halves are tiny, but it
   is honest.
3. **Report v1 and v2 side by side and label the v2 figure as in-sample.** The
   weakest option, acceptable only if stated as such every time it is quoted.

Whichever is chosen, record it here. A number without its provenance is what
got this project into trouble the first time.

### Decision (2026-08-24): option 3, with option 1 still open

**Option 3 is what is implemented, because it is the only one available without
the reviewer.** Option 1 remains the clean answer and is still the recommended
next step — it needs eleven-plus new labels written before any LLM score is
seen, which only the reviewer can produce.

`run_evaluation.py --compare` implements option 3 and enforces its condition
rather than trusting anyone to remember it:

```bash
python scripts/run_evaluation.py --dimension evasiveness \
    --compare evasiveness-v1 --compare evasiveness-v2
```

- Every run prints an **IN-SAMPLE** banner. It is not suppressible.
- The **model is held constant** (default: the configured `LLM_MODEL_NAME`).
  Without this the "v1" column would be a three-model mix and the delta would
  measure the model switch, not the prompt — the same confound as BLOCKER-2.
- The comparison is **restricted to transcripts scored under every version**,
  and says how many it excluded. Scoring one prompt on 11 transcripts and the
  other on 3, then printing the columns side by side, compares the transcripts
  rather than the prompts.
- It **warns when fewer than 5 transcripts** are common to all versions.

One consequence worth planning for: `evasiveness-v1` exists on the pinned model
for only 3 transcripts. So even once the v2 sweep covers all 11, a like-for-like
v1-vs-v2 comparison covers **3**. A clean 11-vs-11 prompt comparison requires
re-scoring v1 on the pinned model across all 11 — a second ~220k tokens, about
another day of free-tier quota. Until that is spent, v2's headline number is its
absolute result against the 11 labels, and the v1 baseline for context is the
`--against reviewed` figure in § 0 (MAE 1.73), which changed model as well as
prompt and must be quoted with that caveat.

## 2. What would move the result

The evaluation runs and the answer is negative. The useful question is no
longer "how do we measure this" but "what would make it pass".

In rough order of expected value:

1. ✅ **Prompt revised — `evasiveness-v2` written, unproven.** It addresses the
   four measured failures: a reasoned refusal is explicitly not a dodge; tone
   is explicitly not evasiveness; the model is pushed to use the full 1–10
   range (LLM scores spanned 4–7, human 2–9); and it is told to weigh the
   proportion of questions handled rather than the worst single moment.

   Registered alongside v1 in `src/scoring/prompts.py`. **v1 remains the
   default** — switching silently would invalidate the existing series without
   anyone choosing to. Run it with:

   ```bash
   python scripts/run_all_scoring.py --dimension evasiveness        --prompt-version evasiveness-v2
   ```

   Then evaluate, mindful of § 1.5. Whether v2 is actually better is unmeasured
   — it costs ~220k tokens to find out, just over one day of free-tier budget.
2. **Reconsider batch averaging.** LLM scores cluster in 4–7 while human scores
   span 2–9. Averaging 4–5 independent batch judgements pulls everything toward
   the middle, which caps how well any prompt can correlate
   (`SCORING_METHODOLOGY.md` § 3). Scoring the whole Q&A in one call on a
   large-context model would test this directly.
3. **Measure the current model.** These numbers describe
   `llama-3.3-70b-versatile`, now retired. `openai/gpt-oss-120b` is unmeasured.
4. **More labels.** n=11 with 4 adjacent-quarter pairs is thin. More
   transcripts, ideally labelled *before* seeing the LLM score, would narrow
   the error bars — but this is worth less than fixing the prompt, because the
   current signal is not marginal, it is near zero.

---

## 3. Evaluation protocol (to build)

### 3.1 Ground-truth file

`notebooks/labels.csv` **exists and is pre-filled** — generated from
`reading-notes.md`, one row per reviewed transcript:

```csv
company,quarter,year,dimension,human_score,confidence,llm_score_at_review,reviewer_accuracy_rating,reviewer_verdict,notes_ref
INFY,Q1,2023,evasiveness,,,7,3,Doesnt match,reading-notes.md#infy-q1-2023
```

- `human_score` — **blank, and the only thing missing.** Integer 1–10 on the
  same scale the prompt uses: what the reviewer thinks the score *should* be
- `confidence` — high / medium / low; low-confidence rows reported separately
- the remaining columns are carried over from the existing review so the
  context travels with the number

Label **before** looking at the LLM score wherever possible. These 11 rows were
written with the LLM score visible, which anchors judgement — record that as a
known limitation of the first label set rather than pretending otherwise.

Label **before** looking at the LLM score wherever possible. The existing 11
rows were written with the LLM score visible, which anchors judgment — record
that as a known limitation of the first label set rather than pretending
otherwise.

### 3.2 Metrics

Against a fixed `(model_name, prompt_version)` slice of the `scores` table:

| Metric | What it answers | Target for "usable" |
|---|---|---|
| **MAE** (mean absolute error) | How far off is a typical score? | ≤ 1.5 points on a 1–10 scale |
| **Spearman ρ** | Does it rank transcripts in the right order? | ≥ 0.6 |
| **Within-2 accuracy** | Fraction of scores within ±2 of the human | ≥ 0.7 |
| **Directional agreement** | Do QoQ deltas share the human's sign? | ≥ 0.7 — this is what the product actually claims |

Ranking matters more than absolute calibration here. The product's claim is
"this quarter is worse than last quarter", not "this quarter is a 7".
Directional agreement on deltas is therefore the metric that decides whether
Phase 3 means anything.

### 3.3 Self-consistency — run, result positive

`scripts/run_self_consistency.py` scores one transcript N times with the same
model and prompt and reports the spread. The spread is the noise floor: any
quarter-over-quarter movement smaller than it is indistinguishable from the
model talking to itself.

**Result — TCS Q1 2025, evasiveness, `openai/gpt-oss-120b`, 5 runs:**

```
  scores : [8, 8, 8, 8, 8]
  mean   : 8.00
  range  : 8-8  (spread 0)
  stdev  : 0.00
```

Identical every time. At temperature 0.1 this model is effectively
deterministic on this transcript, so the `±1.5` trend thresholds in
`src/trends/metrics.py` sit **above** the noise floor rather than inside it.
Phase 3's IMPROVING/DETERIORATING labels are therefore capable of carrying
signal — which was the open question that blocked everything downstream.

Two caveats worth keeping:

- One transcript, one dimension. Repeat on others before generalising; the
  script takes `--company/--quarter/--year/--dimension/--runs`.
- Determinism is not accuracy. The model returns the same answer every time;
  the human review says that answer is often the wrong one. Consistency makes
  the trend layer *meaningful*, not *correct*.

Worth noting: this same transcript scored 6 under `llama-3.3-70b-versatile`,
7 under `allam-2-7b`, and 8 under `openai/gpt-oss-120b`. Run-to-run variance is
zero; **cross-model variance is 2 points.** The model choice matters far more
than sampling noise, which is exactly why the comparability rule in
`SCORING_METHODOLOGY.md` § 4 exists.

### 3.3a What an evaluation actually costs

Measured during the first sweep, and it constrains everything above:

| | |
|---|---|
| Tokens per dimension-score | ~20,000 |
| A full 11 × 5 sweep | ~1.1M tokens |
| Free-tier daily budget | 200,000 |
| **Days of free quota for one full sweep** | **~5** |

Any evaluation plan that assumes scoring is cheap is wrong. Scope the ground
truth to what can actually be scored on one model: a complete series over
*fewer* transcripts beats a partial series over all of them, because the
metrics in § 3.2 need a comparable series to run against at all. See
`KNOWN_ISSUES.md` BLOCKER-4.

### 3.4 Model comparison

The DB has accidentally produced a three-model comparison on evasiveness.
Turn the accident into an experiment: score all 11 transcripts with each
candidate model at a pinned prompt version, then compare each against the
human labels via the metrics above. Pick one model. Pin it. Record the choice
in `SCORING_METHODOLOGY.md`.

### 3.5 Harness — built

`scripts/run_evaluation.py`, with the metrics in `src/evaluation/metrics.py`
and 24 tests. No new dependency: Spearman comes from pandas' rank correlation
rather than scipy, keeping `PROJECT_RULES.md`'s small-stack constraint.

```bash
python scripts/run_evaluation.py
python scripts/run_evaluation.py --dimension evasiveness --json
```

It refuses to run (exit 2) against a dimension whose scores span multiple
models, because the error would partly measure the model switch;
`--allow-mixed-models` overrides. It fails clearly when the labels file is
missing or has no `human_score` filled in, rather than reporting metrics
computed over nothing.

Three deliberate choices about absent data, since this file exists to stop the
project fooling itself:

- Spearman returns `None`, not `0.0`, when a column has no variance to rank —
  `0.0` would read as a measured result rather than an absent one
- blank `human_score` rows are dropped, never read as zero
- the report prints an explicit note when `n < 5`, or when there are no
  adjacent-quarter pairs and directional agreement is therefore unmeasured

**It is ready and currently refuses to run**, because `notebooks/labels.csv`
has no `human_score` values. That is the correct behaviour and the honest
state of the project.

Note the empty `.deepeval/` directory: an eval framework was scaffolded once
and abandoned; do not resurrect it.

---

## 4. Acceptance criteria

Phase 2 is not "done" because five modules exist. It is done when, for a
single pinned model and prompt version:

- [ ] All 11 transcripts × 5 dimensions scored in one run (55 scores, one model)
- [ ] `notebooks/labels.csv` holds a human score for all 11 evasiveness rows
- [ ] Self-consistency spread measured and recorded
- [ ] MAE, Spearman, within-2, and directional agreement computed and recorded
- [ ] The result is written down **whatever it says** — a documented failure is
      a valid outcome and is more useful than an undocumented success

Only then does `data/findings/findings.md` — the one demonstrable
trend-to-stock-move case study — mean anything. Filling it in before this is
complete would be a story, not a finding.

---

## 5. Honest current standing

> The evasiveness dimension has been scored on 11 transcripts and reviewed by
> a human on all 11. The human judged the LLM's score accurate on 3 of them.
> The other four dimensions have between 1 and 4 data points each and no
> review at all. No error metric, no consistency measurement, and no
> stock-price validation has been run. **The scores are not yet evidence of
> anything.**

Keep that paragraph accurate. If it ever becomes possible to write a stronger
one, that is the project working.
