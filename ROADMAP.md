# ROADMAP.md

_Ordering respects the sequential-phase rule in `PROJECT_RULES.md`. Rewritten
2026-08-23 after verifying every phase against the running code — the previous
version planned Phases 3 and 4 that had already shipped, and listed a human
review that had already been completed._

All four phases now have code. The work ahead is not "build the next phase" —
it is **making the numbers trustworthy**, because every claim the project makes
depends on scores that have never been validated.

---

## Step 0 — Unbreak (a few hours, no LLM calls)

Do these first; they are cheap and everything downstream depends on them.

1. **Fix `scripts/run_trends.py`** — add the missing `sys.path.insert` prelude.
   One line. The documented Phase 3 CLI has never run. (KNOWN_ISSUES.md BLOCKER-1)
2. **Fix `test_sentiment_shift_score_key_in_result`** — mock it like the test
   below it. Until then the suite fails offline and CI green is meaningless.
   (HIGH-1)
3. **Back up `data/earningslens.db`.** The 20 scores in it cost real API calls
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
5. **Measure self-consistency before spending more on scoring.** Score one
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
7. **Add the numeric human labels.** `notebooks/reading-notes.md` already has a
   full written review of all 11 evasiveness transcripts; only the "Your Score"
   column is blank. Eleven numbers, from transcripts already read. This is the
   highest value-per-minute task in the project — without it, error cannot be
   computed at all. Export to `notebooks/labels.csv`. (`EVALUATION.md` § 3.1)
8. **Build `scripts/run_evaluation.py`** — MAE, Spearman ρ, within-2 accuracy,
   and directional agreement on QoQ deltas. Logic in `src/evaluation/`,
   orchestration in the script. No new dependencies, no eval framework.
   (`EVALUATION.md` § 3.5)
9. **Write the result down whatever it says.** A documented failure is a real
   outcome; an undocumented success is not.

---

## Step 2 — Make the trend layer correct

Only worth doing once Step 1 shows the scores carry signal.

10. **Gap-aware deltas.** INFY's quarters are not contiguous; `diff()` currently
    reports a four-quarter jump as quarter-over-quarter. Emit `NaN` when the
    period distance is not 1. (HIGH-3)
11. **Fix the sort key** in `src/trends/metrics.py` — it applies the period key
    to the `company` column, so companies interleave and per-company diffs are
    correct only by accident. (MEDIUM-1)
12. **Re-derive the trend thresholds** from the self-consistency measurement in
    step 5 instead of the current arbitrary ±1.5.
13. **Guard the trend layer against mixed models** — `load_scores_from_db()`
    should refuse, loudly, to build a series spanning more than one
    `(model_name, prompt_version)` per dimension.

---

## Step 3 — Fix the schema before the next ingest

14. **Give transcripts a real identity.** `transcripts` is a chunks table;
    scores are keyed to the rowid of chunk 0, and re-running `run_phase1.py`
    silently orphans every score. Either split into `transcripts` + `chunks`, or
    key `scores` on `(company, quarter, year)`. Do this **before** ingesting
    anything new. (HIGH-2)

---

## Step 4 — The verification milestone

15. **Populate `data/findings/findings.md`** with one real, verified
    trend-to-stock-move case. This is the project's "does this actually work"
    checkpoint. It is only meaningful after Steps 1–2; filling it before then
    produces a story, not a finding.

---

## Step 5 — Housekeeping (any time)

16. Move `check_evasiveness.py` into `scripts/` or delete it; remove the stray
    `0` file; gitignore `.deepeval/`.
17. Run `mypy src/` in CI — the config exists and is never invoked. Align the
    Python version (`mypy.ini` says 3.12, CI runs 3.11).
18. Collapse the two divergent "score all dimensions" implementations
    (`score_transcript_all()` vs the loop in `run_all_scoring.py`) into one.
    (MEDIUM-4)
19. Enforce or delete `config.COMPANIES` — it declares WIPRO and HDFCBANK, which
    are ingested nowhere and checked nowhere.

---

## Explicitly deferred (see FUTURE_IDEAS.md)

- Expanding beyond TCS/INFY. **More companies will not make the scores more
  trustworthy** — validation on the 11 transcripts already ingested comes first.
- Multi-user support, auth, or a hosted deployment.
- Any retrieval/vector/LangChain approach — hard constraints, not deferrals.
