"""
Drive a scoring sweep to completion across a rolling token budget.

A full sweep does not fit in the free tier's daily allowance (KNOWN_ISSUES.md
BLOCKER-4). The cap is a rolling 24-hour window, so capacity frees up
gradually as older usage ages out rather than all at once at midnight --
which means a sweep can be finished in slices without a human sitting on it.

This wrapper runs `run_all_scoring.py --skip-scored` in a loop:

    exit 0  -> the sweep is complete, stop
    exit 3  -> token budget exhausted, wait and retry
    other   -> retry too, unless several consecutive attempts land no scores

Everything already scored is kept between attempts, so each retry costs only
the transcripts that still need work.

The last case matters more than it looks. A transient network fault once failed
6 transcripts in a row and ended the whole plan, with the API reachable again
moments later. Progress -- not the exit code -- is what separates a blip from a
real fault, so the loop retries while scores keep landing and gives up only
after --max-stalls consecutive attempts achieve nothing.

Usage:
    python scripts/resume_sweep.py --dimension evasiveness \
        --prompt-version evasiveness-v2

    python scripts/resume_sweep.py --dimension evasiveness --wait-minutes 30 \
        --max-hours 12

Stop it at any time with Ctrl-C; scores already written are durable.
"""

import argparse
import logging
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import LOG_PATH  # noqa: E402
from src.utils.logging import setup_logger  # noqa: E402

logger = logging.getLogger("earningslens")

EXIT_COMPLETE = 0
EXIT_BUDGET_EXHAUSTED = 3

_RUNNER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_all_scoring.py")


def build_command(args) -> list[str]:
    """The inner scoring command. --skip-scored is what makes a retry cheap."""
    cmd = [sys.executable, _RUNNER, "--skip-scored"]
    for dimension in args.dimension or []:
        cmd += ["--dimension", dimension]
    for version in args.prompt_version or []:
        cmd += ["--prompt-version", version]
    if args.company:
        cmd += ["--company", args.company]
    if args.model:
        cmd += ["--model", args.model]
    return cmd


def count_scored(args) -> int:
    """How many scores the target slice holds right now.

    Progress, not the exit code, is what distinguishes a transient fault from a
    real one: a run that keeps landing scores is worth retrying however it
    exited.
    """
    import sqlite3

    from config import DB_PATH, LLM_MODEL_NAME

    sql = "SELECT COUNT(*) FROM scores WHERE company IS NOT NULL"
    params: list = []
    if args.dimension:
        sql += f" AND dimension IN ({','.join('?' * len(args.dimension))})"
        params += args.dimension
    if args.prompt_version:
        sql += f" AND prompt_version IN ({','.join('?' * len(args.prompt_version))})"
        params += args.prompt_version
    model = args.model or LLM_MODEL_NAME
    if model:
        sql += " AND model_name = ?"
        params.append(model)

    try:
        conn = sqlite3.connect(str(DB_PATH))
        try:
            return int(conn.execute(sql, params).fetchone()[0])
        finally:
            conn.close()
    except sqlite3.Error:
        # Never let a bookkeeping query end the sweep.
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a scoring sweep to completion, waiting out token budget limits.",
    )
    parser.add_argument("--dimension", action="append",
                        help="Dimension to score (repeatable). Passed through to run_all_scoring.")
    parser.add_argument("--prompt-version", action="append",
                        help="Prompt version to use (repeatable). Passed through.")
    parser.add_argument("--company", help="Restrict to one company. Passed through.")
    parser.add_argument("--model", help="Override the model. Passed through.")
    parser.add_argument("--wait-minutes", type=int, default=20,
                        help="How long to wait after a budget stop before retrying (default: 20).")
    parser.add_argument("--max-hours", type=float, default=24.0,
                        help="Give up after this long (default: 24). Scores written are kept.")
    parser.add_argument("--retry-seconds", type=int, default=60,
                        help="Wait after a transient (non-budget) failure before retrying "
                             "(default: 60).")
    parser.add_argument("--max-stalls", type=int, default=4,
                        help="Give up after this many consecutive non-budget attempts that "
                             "land no new scores (default: 4). A run still making progress "
                             "never counts as stalled.")
    parser.add_argument("--max-attempts", type=int, default=200,
                        help="Backstop against an unexpected retry loop (default: 200).")
    args = parser.parse_args()

    setup_logger(LOG_PATH)

    cmd = build_command(args)
    deadline = time.monotonic() + args.max_hours * 3600
    logger.info("Resuming sweep: %s", " ".join(cmd[1:]))
    logger.info("Waiting %d min between budget stops, giving up after %.1f h.",
                args.wait_minutes, args.max_hours)

    stalls = 0
    for attempt in range(1, args.max_attempts + 1):
        logger.info("--- attempt %d ---", attempt)
        scored_before = count_scored(args)
        result = subprocess.run(cmd)

        if result.returncode == EXIT_COMPLETE:
            logger.info("Sweep complete after %d attempt(s).", attempt)
            return 0

        if result.returncode != EXIT_BUDGET_EXHAUSTED:
            # A transient provider or network fault must not end a multi-day
            # plan. Measured: one connection blip failed 6 transcripts in a row
            # and aborted the whole run, with the API reachable again moments
            # later. Retry while attempts are still landing scores, and give up
            # only once several consecutive attempts have achieved nothing --
            # which is what a real, persistent failure looks like.
            scored_now = count_scored(args)
            if scored_now > scored_before:
                stalls = 0
                logger.warning(
                    "Exit %d, but %d new score(s) landed — treating as transient, retrying.",
                    result.returncode, scored_now - scored_before)
            else:
                stalls += 1
                logger.warning(
                    "Exit %d with no progress (%d/%d consecutive). Retrying.",
                    result.returncode, stalls, args.max_stalls)

            if stalls >= args.max_stalls:
                logger.error(
                    "%d consecutive attempt(s) made no progress — this is not transient. "
                    "Stopping. Scores already written are kept.", stalls)
                return result.returncode

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                logger.warning("Reached the %.1f h limit. Scores written are kept.",
                               args.max_hours)
                return result.returncode
            wait_seconds = min(args.retry_seconds, remaining)
            logger.info("Waiting %.0f s before retrying.", wait_seconds)
            time.sleep(wait_seconds)
            continue

        stalls = 0

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            logger.warning(
                "Reached the %.1f h limit with work still outstanding. "
                "Scores already written are kept; re-run to continue.", args.max_hours)
            return EXIT_BUDGET_EXHAUSTED

        wait_seconds = min(args.wait_minutes * 60, remaining)
        logger.info("Budget exhausted. Waiting %.0f min, then retrying (%.1f h left).",
                    wait_seconds / 60, remaining / 3600)
        time.sleep(wait_seconds)

    logger.warning("Hit the %d-attempt backstop with work still outstanding.", args.max_attempts)
    return EXIT_BUDGET_EXHAUSTED


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.warning("Interrupted. Scores already written are kept; re-run to continue.")
        sys.exit(130)
