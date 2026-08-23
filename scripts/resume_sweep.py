"""
Drive a scoring sweep to completion across a rolling token budget.

A full sweep does not fit in the free tier's daily allowance (KNOWN_ISSUES.md
BLOCKER-4). The cap is a rolling 24-hour window, so capacity frees up
gradually as older usage ages out rather than all at once at midnight --
which means a sweep can be finished in slices without a human sitting on it.

This wrapper runs `run_all_scoring.py --skip-scored` in a loop:

    exit 0  -> the sweep is complete, stop
    exit 3  -> token budget exhausted, wait and retry
    other   -> a real failure, stop and surface it

Everything already scored is kept between attempts, so each retry costs only
the transcripts that still need work.

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
    parser.add_argument("--max-attempts", type=int, default=200,
                        help="Backstop against an unexpected retry loop (default: 200).")
    args = parser.parse_args()

    setup_logger(LOG_PATH)

    cmd = build_command(args)
    deadline = time.monotonic() + args.max_hours * 3600
    logger.info("Resuming sweep: %s", " ".join(cmd[1:]))
    logger.info("Waiting %d min between budget stops, giving up after %.1f h.",
                args.wait_minutes, args.max_hours)

    for attempt in range(1, args.max_attempts + 1):
        logger.info("--- attempt %d ---", attempt)
        result = subprocess.run(cmd)

        if result.returncode == EXIT_COMPLETE:
            logger.info("Sweep complete after %d attempt(s).", attempt)
            return 0

        if result.returncode != EXIT_BUDGET_EXHAUSTED:
            logger.error("Scoring failed with exit %d — not a budget stop. Stopping.",
                         result.returncode)
            return result.returncode

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
