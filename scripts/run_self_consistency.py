"""Measure how much a dimension's score varies across identical repeated runs.

Temperature is 0.1, not 0, so the same transcript scored twice can differ. That
spread is the noise floor: any quarter-over-quarter movement smaller than it is
indistinguishable from the model talking to itself.

This matters because src/trends/metrics.py labels a quarter IMPROVING or
DETERIORATING at a delta of +/-1.5. If the run-to-run spread approaches that,
the labels are noise and Phase 3 means nothing. Ten-odd calls can establish
this before committing to a full ~250-call scoring sweep.

Nothing is written to the database -- this only measures.

Usage:
    python scripts/run_self_consistency.py
    python scripts/run_self_consistency.py --company INFY --year 2024 --quarter Q2
    python scripts/run_self_consistency.py --dimension overpromising --runs 3
"""

import argparse
import logging
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import DB_PATH, LOG_PATH, LLM_MODEL_NAME, SCORE_DIMENSIONS
from src.storage.db import init_db, get_chunks
from src.scoring import DIMENSION_MODULES, SCORE_KEY_MAP
from src.utils.logging import setup_logger

logger = logging.getLogger("earningslens")

# The trend thresholds this measurement is here to justify.
_TREND_THRESHOLD = 1.5


def score_once(dimension: str, chunks: list[str], model: str | None) -> int | None:
    """Run one scoring pass and return the score, or None if it failed."""
    scorer = DIMENSION_MODULES[dimension]
    result = scorer(chunks, model=model)
    llm_result = result.get("llm_result", result)
    return llm_result.get(SCORE_KEY_MAP[dimension])


def main():
    parser = argparse.ArgumentParser(
        description="Measure run-to-run score spread for one transcript and dimension."
    )
    parser.add_argument("--company", default="TCS")
    parser.add_argument("--quarter", default="Q1")
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--dimension", default="evasiveness", choices=SCORE_DIMENSIONS)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--model", help="Override the model from .env")
    args = parser.parse_args()

    setup_logger(LOG_PATH)
    conn = init_db(str(DB_PATH))
    rows = get_chunks(conn, args.company, args.quarter, args.year)
    conn.close()

    if not rows:
        print(f"No chunks for {args.company} {args.quarter} {args.year}.", file=sys.stderr)
        sys.exit(1)

    chunks = [r[5] for r in rows]
    model = args.model or LLM_MODEL_NAME

    print(f"Self-consistency: {args.company} {args.quarter} {args.year} / {args.dimension}")
    print(f"Model: {model} | {len(chunks)} chunks | {args.runs} runs\n")

    scores: list[int] = []
    for i in range(1, args.runs + 1):
        started = time.time()
        score = score_once(args.dimension, chunks, model)
        elapsed = time.time() - started
        if score is None:
            print(f"  run {i}: FAILED ({elapsed:.1f}s)")
            continue
        scores.append(score)
        print(f"  run {i}: {score}/10 ({elapsed:.1f}s)")

    if len(scores) < 2:
        print("\nNot enough successful runs to measure spread.", file=sys.stderr)
        sys.exit(1)

    spread = max(scores) - min(scores)
    stdev = statistics.stdev(scores)

    print(f"\n  scores : {scores}")
    print(f"  mean   : {statistics.mean(scores):.2f}")
    print(f"  range  : {min(scores)}-{max(scores)}  (spread {spread})")
    print(f"  stdev  : {stdev:.2f}")

    print(f"\n  Trend labels fire at a delta of +/-{_TREND_THRESHOLD}.")
    if spread >= _TREND_THRESHOLD:
        print(f"  VERDICT: spread ({spread}) meets or exceeds the threshold.")
        print("  Trend labels are inside the noise floor -- a quarter can flip")
        print("  IMPROVING/DETERIORATING without anything changing. Raise the")
        print("  thresholds above the measured spread, or average repeated runs.")
    else:
        print(f"  VERDICT: spread ({spread}) is below the threshold.")
        print("  Trend labels are distinguishable from run-to-run noise for this")
        print("  transcript. Repeat on others before generalising.")


if __name__ == "__main__":
    main()
