# ROADMAP.md

_Ordering respects the sequential-phase rule in `PROJECT_RULES.md`. Rewritten
2026-08-23 after verifying every phase against the running code — the previous
version planned Phases 3 and 4 that had already shipped, and listed a human
review that had already been completed._

All four phases now have code. The work ahead is not "build the next phase" —
it is **making the numbers trustworthy**, because every claim the project makes
depends on scores that have never been validated.

---

## Step 0 — Unbreak ✅ done

1. ✅ **Fixed `scripts/run_trends.py`** — add the missing `sys.path.insert` prelude.
   One line. The documented Phase 3 CLI has never run. (KNOWN_ISSUES.md BLOCKER-1)
2. ✅ **Fixed the tests that made live API calls** — four of them, not one.
   (HIGH-1)
3. ✅ **Backed up `data/earningslens.db`.** The 20 scores in it cost real API calls
   and cannot be regenerated from anything local.

---

## Step 1 — Make one dimension trustworthy (the real Phase 2 finish)

Phase 2 is not done because five modules exist. It is done when one dimension
has a valid, measured score series.

4. **Pin a model that still exists.** The configured
   `llama-3.3-70b-versatile` has been retired by Groq and 404s, so *no scoring
   can run at all* right now — and it produced 8 of the 11 evasiveness scores,
   which are consequently unreproducible. Pick from what the key can reach
   (`openai/gpt-oss-120b` is the strongest available), put it in `.env`, record
   it with the date in `SCORING_METHODOLOGY.md`, and never mix again.
   (BLOCKER-3, BLOCKER-2)
5. ✅ **Self-consistency measured** — spread 0 over 5 runs. Score one
   transcript five times at temperature 0.1 and record the spread. ~10 calls.
   If the spread approaches ±2, the ±1.5 trend thresholds are inside the noise
   floor and Phase 3's labels mean nothing — better to learn that now than
   after a 250-call sweep. (`EVALUATION.md` § 3.3)
6. **Re-score onto the pinned model — but a full sweep does not fit in one day.**
   Measured: ~20k tokens per dimension-score, 55 needed, against a 200,000
   token/day free-tier cap. That is **~1.1M tokens, roughly five days of
   quota** (`KNOWN_ISSUES.md` BLOCKER-4). Currently 24/55 scored, of which 10
   are on the pinned model and 3 transcripts are complete.

   Pick a path before spending more:
   - **Narrow the scope.** A contiguous 4-quarter TCS run across all 5
     dimensions (~400k tokens, ~2 days) would actually demonstrate the trend
     feature, which today's sparse coverage cannot. Or evasiveness alone
     across all 11 (~220k) — the only dimension with human review behind it.
   - **Spread it.** Re-run with `--skip-existing` as quota frees; it now stops
     cleanly and exits 3 rather than grinding.
   - **Upgrade the tier.** The only route to a complete series quickly.

   Until one series is complete on one model, the trend layer has nothing
   valid to read.
7. ✅ **Numeric human labels added 2026-08-29.** `labels.csv` now carries a
   `human_score` for all 11 evasiveness transcripts, so error can be computed
   against every model/prompt variant. Done: the evaluation runs; see BLOCKER-6
   for the result — the labels now expose a scorer that does not discriminate,
   which is the current release gate.
8. ✅ **`scripts/run_evaluation.py` built** — MAE, Spearman ρ, within-2, and
   directional agreement, with logic in `src/evaluation/` and 24 tests. Refuses
   to evaluate a dimension whose scores span multiple models, and fails clearly
   when labels are missing or unfilled. Runs the moment step 7 is done.
9. **Write the result down whatever it says.** A documented failure is a real
   outcome; an undocumented success is not.

---

## Step 2 — Make the trend layer correct

Only worth doing once Step 1 shows the scores carry signal.

10. ✅ **Gap-aware deltas.** INFY's quarters are not contiguous; `diff()` currently
    reports a four-quarter jump as quarter-over-quarter. Emit `NaN` when the
    period distance is not 1. (HIGH-3)
11. ✅ **Fixed the sort key** in `src/trends/metrics.py` — it applies the period key
    to the `company` column, so companies interleave and per-company diffs are
    correct only by accident. (MEDIUM-1)
12. ✅ **Trend thresholds justified.** Self-consistency spread is 0 on the
    pinned model, so ±1.5 clears the noise floor. The measurement is recorded
    beside the constants in `src/trends/metrics.py`, with a warning to
    re-measure if the model changes.
13. ✅ **Trend layer guards against mixed models** — `load_scores_from_db()`
    should refuse, loudly, to build a series spanning more than one
    `(model_name, prompt_version)` per dimension.

---

## Step 3 — Fix the schema before the next ingest

14. ✅ **Transcripts have a real identity.** `transcripts` is a chunks table;
    scores are keyed to the rowid of chunk 0, and re-running `run_phase1.py`
    silently orphans every score. Either split into `transcripts` + `chunks`, or
    key `scores` on `(company, quarter, year)`. Do this **before** ingesting
    anything new. (HIGH-2)

---

## Step 3.5 — Fix what the evaluation exposed ✅ prompt written, unproven

The evaluation came back negative, so the next phase is the prompt, not more
features.

20. ✅ **Prompt versioning made trustworthy.** `prompt_version` was hardcoded,
    so editing a prompt would leave scores stamped v1 and defeat the
    comparability guard. Prompts now live in a registry keyed by version, with
    a checksum test that fails if a prompt is edited without registering a new
    version.
21. ✅ **`evasiveness-v2` written** — targets the four measured failures: a
    reasoned refusal is not a dodge, tone is not evasiveness, use the full
    1–10 range, weigh proportion not worst moment. v1 remains the default.
22. 🟡 **Score with v2 and evaluate it.** ~220k tokens, just over one day of
    free-tier budget. Read `EVALUATION.md` § 1.5 first: the 11 labels informed
    v2's design, so an in-sample number must be reported as in-sample.

    Attempted 2026-08-24. **1 of 11 transcripts scored** before the free-tier
    daily token budget was exhausted; the sweep stopped cleanly at exit 3.
    Resume with `--skip-scored` as quota frees.

    The attempt was worth it for what it exposed: at `max_tokens = 800`,
    v2's longer output truncated and the batch was **silently dropped from the
    average** (`KNOWN_ISSUES.md` HIGH-4, fixed). Had the sweep completed on the
    old code, the v1-vs-v2 comparison would have been biased against v2 by an
    artifact of the token limit rather than by the prompt. Re-run from a clean
    slate on the fixed scorer.

    **§ 1.5 decided (2026-08-24): option 3, implemented and enforced.**
    `run_evaluation.py --compare` prints an unsuppressible IN-SAMPLE banner,
    holds the model constant, and restricts to transcripts scored under every
    version. Option 1 — fresh labels written before any LLM score is seen —
    stays the clean answer and needs the reviewer.

23. 🟡 **Re-score `evasiveness-v1` on the pinned model across all 11.**
    **Measured: 8 transcripts, ~160k tokens** — 3 already have v1 on
    `openai/gpt-oss-120b`, so this is cheaper than the ~220k a full pass costs.
    Without it a like-for-like v1-vs-v2 comparison covers 3, not 11, and v2's
    number stands alone against the labels — the only v1 baseline
    (`--against reviewed`, MAE 1.73) changed model as well as prompt.

    Started 2026-08-24, chained behind step 22. The order matters: v1 must not
    start until v2 completes, or the day's quota is split across two incomplete
    series and neither becomes a valid one.

    ```bash
    python scripts/resume_sweep.py --dimension evasiveness \
        --prompt-version evasiveness-v2 --wait-minutes 18 --max-hours 24 && \
    python scripts/resume_sweep.py --dimension evasiveness \
        --prompt-version evasiveness-v1 --wait-minutes 18 --max-hours 24 && \
    python scripts/run_evaluation.py --dimension evasiveness \
        --compare evasiveness-v1 --compare evasiveness-v2
    ```

    Both passes together are ~360k tokens, about 1.8 days of free-tier quota.

## Step 4 — The verification milestone

15. **Populate `data/findings/findings.md`** with one real, verified
    trend-to-stock-move case. This is the project's "does this actually work"
    checkpoint. It is only meaningful after Steps 1–2; filling it before then
    produces a story, not a finding.

---

## Step 5 — Housekeeping (any time)

16. ✅ Moved `check_evasiveness.py` to `scripts/check_db_status.py`; removed the
    stray `0` file; gitignored `.deepeval/`.
17. ✅ CI runs `mypy src/` and byte-compiles `scripts/`, on Python 3.12.
18. ✅ Collapsed the two divergent "score all dimensions" implementations.
19. ✅ Removed `config.COMPANIES` / `QUARTERS` — both were read nowhere.

---

## Step 6 — Close BLOCKER-6 (the release gate)

Everything above is built and tested; the release gate still exits 3 because
`evasiveness-v2` on the pinned model fails all four targets (Spearman −0.73)
against labels that are now filled in. This is a measurement problem, not a
missing feature. There is exactly one way to change the verdict: score under a
new variant and re-measure. The plan below is the concrete sequence, costing
quotient included, so each step is a decision you can make before spending.

Cost of everything here, summed: ~2 v3 sweep-passes (~440k tokens, ~2.2 days)
plus ~1 v1 baseline pass (~200k tokens, ~1 day), roughly **3.2 days of free-tier
budget**, spread across the rolling 24-hour window with `resume_sweep.py`.

### Step 6a — Measure evasiveness-v3 (why it exists: a per-exchange unit)

v3 scores each analyst exchange, keeps every per-exchange score, and aggregates
in code rather than by averaging whole-call windows. It costs the same as a v2
sweep and is the first variant that treats the human labels (a
worst-moments judgement) as commensurable with the machine measure. It has been
built and tested but **never scored against real transcripts** — this is the
cheapest unexercised lever available.

```bash
# 1. Score all 11 transcripts under v3 on the pinned model (~220k, ~1.1 days).
python scripts/resume_sweep.py --dimension evasiveness \
    --prompt-version evasiveness-v3 --wait-minutes 18 --max-hours 24

# 2. Re-aggregate under every aggregator and re-measure vs the labels.
#    Makes NO LLM calls -- every per-exchange score is stored in
#    scores.raw_llm_response.
earningslens-aggregators
```

Read `earningslens-aggregators`:

- **`spread` near 0 under every aggregator** → the model does not discriminate
  at the exchange level either. The rubric, not the aggregation, is the problem.
  Go to Step 6c with that evidence.
- **Healthy `spread`, Spearman still negative** → v3 separates transcripts but
  ranks them against the reviewer. The rubric or the label unit is off. Go to
  Step 6c / 6d.
- **A `spread` and Spearman that now pass** → the strongest resolution yet, but
  **not out-of-sample**: the labels informed v1/v2 design and the v3 default
  aggregator was chosen to match them (EVALUATION.md § 1.5). Hold the result and
  go to Step 6d before claiming victory.

### Step 6b — Re-measure v1 on the pinned model for a like-for-like comparison

The only positive-Spearman evidence so far (0.10) came from `--against reviewed`
on llama-3.3-70b, a model that no longer exists. To know whether the pinned
model itself can rank, v1 needs scores on the pinned model across all 11.

```bash
python scripts/resume_sweep.py --dimension evasiveness \
    --prompt-version evasiveness-v1 --wait-minutes 18 --max-hours 24

python scripts/run_evaluation.py --dimension evasiveness --against reviewed
```

### Step 6c — Attack the rubric/unit if no variant discriminates

Order of expected value, from KNOWN_ISSUES.md BLOCKER-6:

1. **Stop asking a fragment to judge the whole.** v3 already does this per
   exchange; if v3 also fails, the failure is inside the rubric it shares with
   v1/v2.
2. **Force the range.** Anchored rubrics with worked examples at 2, 5 and 9, or
   forced pairwise ranking of transcripts, attacks the 5–6 collapse directly.
3. **New labels against a stated unit.** The current 11 labels are a
   worst-three-moments judgement; every whole-call statistic is incommensurable
   with them by construction. Fresh labels scored against *whole transcripts*,
   or per-exchange labels against per-exchange scores, would make the metric
   itself honest. This needs a careful human reader and is the only route to a
   genuinely out-of-sample verdict.

### Step 6d — The out-of-sample requirement

Nobody should call a variant "validated" on labels that informed its design.
Once a variant passes on an in-sample split, hold out labels gathered without
seeing that variant's output, and only then treat the four-target pass as a
release signal.

### Step 6e — The release gate, mechanically

```bash
python scripts/run_evaluation.py --dimension evasiveness --against reviewed
echo $?    # 0 → the credibility claim is shippable; anything else → it is not.
```

Exit 0 (all four targets met) is the only state in which CI's `release-gate`
job passes and `image-publish` pushes a Docker Hub image. The gate ordering is
already wired — a red gate simply skips the publish. This roadmap is done when
that number is 0 on a held-out label set.

---

## Explicitly deferred (see FUTURE_IDEAS.md)

- Expanding beyond TCS/INFY. **More companies will not make the scores more
  trustworthy** — validation on the 11 transcripts already ingested comes first.
- Multi-user support, auth, or a hosted deployment.
- Any retrieval/vector/LangChain approach — hard constraints, not deferrals.
