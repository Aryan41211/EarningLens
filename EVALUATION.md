# EVALUATION.md

How to tell whether EarningsLens actually works. This is the missing piece the
whole project rests on: every claim it makes — "management is getting more
evasive", "this trend preceded a stock move" — is only worth as much as the
scores behind it, and those scores have never been measured against anything.

`EXPERIMENTS.md` records research that has been *run*. This file defines the
evaluation that has *not* been run, plus the evidence that already exists.

---

## 1. What evidence exists today

### 1.1 The human review set (real, and better than the docs claim)

`notebooks/reading-notes.md` contains a completed human review of all 11
evasiveness-scored transcripts. For each: three LLM supporting quotes, a 1–10
rating of *how accurate the LLM's score was*, a written justification, a
"key missed context" note, and a verdict.

| Transcript | LLM score (as reviewed) | Human accuracy rating | Verdict |
|---|---|---|---|
| INFY Q1 2023 | 7 | 3 / 10 | Doesn't match |
| INFY Q1 2024 | 6 | 2 / 10 | Doesn't match |
| INFY Q2 2024 | 6 | 9 / 10 | Doesn't match |
| INFY Q4 2025 | 6 | 3 / 10 | Doesn't match |
| TCS Q2 2023 | 6 | 4 / 10 | Doesn't match |
| TCS Q3 2023 | 6 | 5 / 10 | Partially |
| TCS Q1 2024 | 7 | 6 / 10 | Partially |
| TCS Q2 2024 | 4 | 4 / 10 | Matches |
| TCS Q3 2024 | 6 | 5 / 10 | Partially |
| TCS Q1 2025 | 6 | 6 / 10 | Matches |
| TCS Q4 2025 | 4 | 4 / 10 | Matches |

**Mean human accuracy rating: 4.6 / 10.** Verdicts: 3 Matches, 3 Partially,
5 Doesn't match — the LLM agrees with the human read on **3 of 11**
transcripts (27%). Every INFY review came back "Doesn't match".

This is a real, negative, useful result. It should be treated as the project's
current headline finding, not as a gap.

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

## 2. The gap that blocks a real evaluation

The review captured **how wrong** the LLM was, not **what right looks like**.
The "Your Score" column in the summary table is still blank for all 11 rows.

Without a human 1–10 evasiveness score per transcript there is no ground truth
to compute error against — only an aggregate opinion that the model is ~4.6/10
trustworthy. Filling that one column is the cheapest high-value task in the
entire project: 11 numbers, from transcripts already read, by a reviewer who
has already written the justification.

---

## 3. Evaluation protocol (to build)

### 3.1 Ground-truth file

Machine-readable, so the harness never parses prose. Proposed
`notebooks/labels.csv`:

```csv
company,quarter,year,dimension,human_score,confidence,notes_ref
INFY,Q1,2023,evasiveness,7,high,reading-notes.md#infy-q1-2023
```

- `human_score` — integer 1–10, the reviewer's own score, same scale as the prompt
- `confidence` — high / medium / low; low-confidence rows are reported separately
- `notes_ref` — anchor back to the written justification

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

### 3.5 Harness shape

Constraints from `PROJECT_RULES.md` still apply — no LangChain, no eval
framework with a service dependency, no sixth dimension.

```
scripts/run_evaluation.py
    --dimension evasiveness
    --model llama-3.3-70b-versatile
    --prompt-version evasiveness-v1
```

Reads `notebooks/labels.csv`, reads the matching slice of `scores`, prints
MAE / Spearman / within-2 / directional agreement, and writes a dated report
to `notebooks/`. Logic in `src/evaluation/`, orchestration only in the script
— the same rule as every other phase. Note the empty `.deepeval/` directory:
an eval framework was scaffolded once and abandoned; do not resurrect it.

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
