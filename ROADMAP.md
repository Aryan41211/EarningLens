# ROADMAP.md

_Ordering respects the sequential-phase rule in `PROJECT_RULES.md` — items
are listed in the order they should be tackled, not by convenience._

## Immediate next steps (finish Phase 2)

1. Add a dedicated `scores` table (per-dimension, per-transcript, queryable
   columns) instead of relying on JSON parsing from `scoring_runs` —
   this unblocks Phase 3 trend math.
2. Implement the remaining 4 scoring dimensions, following the pattern
   established in `src/scoring/evasiveness.py`:
   - Sentiment shift
   - Overpromising
   - Complexity spike (Flesch readability formula planned as a rule-based
     complement to the LLM call)
   - Forward guidance vagueness
3. Start populating `notebooks/reading-notes.md` with real human-labeled
   examples — needed to build any evaluation harness.
4. Build a lightweight evaluation harness comparing LLM scores against the
   human labels above.

## Phase 3 — Trend detection

- QoQ delta computation
- Rolling averages
- Trend classification/labels (improving / stable / deteriorating)
- Spike/drop detection with alerting thresholds
- Implement the 4 stub functions in `src/trends/metrics.py`

## Phase 4 — Dashboard

- Streamlit app: company selector, quarter timeline, per-dimension trend
  lines, chunk-level drill-down, exportable "finding cards"
- Add Streamlit to `requirements.txt` (not yet a dependency)

## Verification milestone

- Populate `data/findings/findings.md` with one real, verified
  trend-to-stock-move case study — this is the project's "does this
  actually work" checkpoint before investing further in Phase 3/4 polish.

## Explicitly deferred (see FUTURE_IDEAS.md)

- Expanding beyond TCS/INFY to Wipro and HDFC Bank (already in `config.py`
  but unenforced/unused)
- Anything resembling multi-user support, auth, or a hosted deployment
