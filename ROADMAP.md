# ROADMAP.md

_Ordering respects the sequential-phase rule in `PROJECT_RULES.md` — items
are listed in the order they should be tackled, not by convenience._

## Immediate next steps (finish Phase 2)

1. **Validate non-evasiveness dimensions on real transcripts** — score a
   small set (e.g., 2-3 TCS quarters) for sentiment_shift, complexity_spike,
   overpromising, and forward_guidance_vagueness. Review output for prompt
   quality, scoring consistency, and edge cases.
2. **Populate `notebooks/reading-notes.md`** with real human-labeled
   examples — needed to build any evaluation harness.
3. **Build a lightweight evaluation harness** comparing LLM scores against
   the human labels above.

*Note: INFY evasiveness scoring is complete — all 4 quarters already scored.*

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
