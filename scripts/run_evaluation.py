"""Compare stored LLM scores against human labels.

This is the check the whole project rests on: EarningsLens claims to detect
management credibility, and until scores are measured against human judgement
that claim is untested.

Reads human labels from a CSV (see EVALUATION.md section 3.1) and the matching
slice of the scores table, then reports MAE, Spearman, within-2 accuracy, and
directional agreement per dimension.

Only compares scores from a single (model, prompt_version) per dimension --
mixing them measures the model change rather than the company, so a
contaminated dimension is refused rather than silently averaged.

Usage:
    python scripts/run_evaluation.py
    python scripts/run_evaluation.py --dimension evasiveness
    python scripts/run_evaluation.py --labels notebooks/labels.csv --json
"""

import argparse
import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd

from config import DB_PATH, LOG_PATH, NOTEBOOKS_DIR, SCORE_DIMENSIONS
from src.storage.db import init_db
from src.evaluation import TARGETS, evaluate, meets_target, pair_scores_with_labels
from src.trends.metrics import check_score_comparability
from src.utils.logging import setup_logger

logger = logging.getLogger("earningslens")

DEFAULT_LABELS = NOTEBOOKS_DIR / "labels.csv"


def load_scores(conn, dimensions: list[str]) -> pd.DataFrame:
    placeholders = ",".join("?" * len(dimensions))
    return pd.read_sql_query(
        f"""
        SELECT company, quarter, year, dimension, score, model_name, prompt_version
        FROM scores
        WHERE dimension IN ({placeholders}) AND company IS NOT NULL
        """,
        conn,
        params=dimensions,
    )


def _fmt(value: float | None, metric: str) -> str:
    """Format a metric with a pass/fail marker against its target."""
    if value is None:
        return "     n/a"
    ok = meets_target(metric, value)
    mark = "" if ok is None else ("  PASS" if ok else "  FAIL")
    return f"{value:8.2f}{mark}"


def print_report(results: dict[str, dict]) -> None:
    print("\n" + "=" * 78)
    print("EVALUATION - LLM scores vs human labels")
    print("=" * 78)
    print(
        f"Targets: MAE <= {TARGETS['mae']}, Spearman >= {TARGETS['spearman']}, "
        f"within-2 >= {TARGETS['within_2']}, direction >= {TARGETS['directional_agreement']}"
    )

    for dimension, m in results.items():
        print(f"\n{dimension}  (n={m['n']})")
        print(f"  MAE                   {_fmt(m['mae'], 'mae')}")
        print(f"  Spearman              {_fmt(m['spearman'], 'spearman')}")
        print(f"  Within 2 points       {_fmt(m['within_2'], 'within_2')}")
        print(
            f"  Directional agreement {_fmt(m['directional_agreement'], 'directional_agreement')}"
            f"   (from {m['n_direction_comparisons']} adjacent-quarter comparison(s))"
        )

        if m["n"] < 5:
            print(f"  NOTE: only {m['n']} labelled pair(s) - too few to conclude anything.")
        if m["n_direction_comparisons"] == 0:
            print("  NOTE: no adjacent-quarter pairs, so the metric that matters most is unmeasured.")

    print("\n" + "=" * 78)


def main():
    parser = argparse.ArgumentParser(description="Evaluate LLM scores against human labels.")
    parser.add_argument("--labels", default=str(DEFAULT_LABELS),
                        help=f"CSV of human labels (default: {DEFAULT_LABELS})")
    parser.add_argument("--dimension", action="append", metavar="NAME",
                        help="Evaluate only this dimension (repeatable). Default: all.")
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--json", action="store_true", help="Also emit results as JSON")
    parser.add_argument("--against", choices=["db", "reviewed"], default="db",
                        help="'db' compares the current scores table. 'reviewed' compares the "
                             "llm_score_at_review column in the labels file -- the scores the "
                             "human actually saw, which stays a clean single-model comparison "
                             "even after the database has been re-scored by other models.")
    parser.add_argument("--allow-mixed-models", action="store_true",
                        help="Evaluate even where a dimension spans multiple models. "
                             "The result measures the model mix, not the company.")
    args = parser.parse_args()

    dimensions = args.dimension or list(SCORE_DIMENSIONS)
    unknown = [d for d in dimensions if d not in SCORE_DIMENSIONS]
    if unknown:
        parser.error(f"unknown dimension(s): {', '.join(unknown)}")

    setup_logger(LOG_PATH)

    if not os.path.exists(args.labels):
        print(
            f"No labels file at {args.labels}.\n"
            "Human labels are what makes evaluation possible; see EVALUATION.md "
            "section 3.1 for the format. notebooks/labels.csv is a pre-filled "
            "template - add a human_score to each row.",
            file=sys.stderr,
        )
        sys.exit(1)

    labels = pd.read_csv(args.labels)
    labelled = labels.dropna(subset=["human_score"]) if "human_score" in labels else labels.iloc[0:0]
    if labelled.empty:
        print(
            f"{args.labels} has no human_score values filled in - nothing to evaluate against.\n"
            "The reviewer rated how accurate the LLM was, but never recorded what the "
            "score should have been. Without that number, error cannot be computed.",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.against == "reviewed":
        # Compare against the scores the reviewer actually saw. The database has
        # since been partly re-scored by other models, so this is the only
        # single-model comparison currently available for evasiveness.
        if "llm_score_at_review" not in labels.columns:
            print("--against reviewed needs an llm_score_at_review column in the labels file.",
                  file=sys.stderr)
            sys.exit(1)
        scores = labels[labels["dimension"].isin(dimensions)].dropna(
            subset=["llm_score_at_review"]
        ).copy()
        scores["score"] = scores["llm_score_at_review"].astype(float)
        scores = scores[["company", "quarter", "year", "dimension", "score"]]
        contaminated = pd.DataFrame()
    else:
        conn = init_db(args.db)
        contaminated = check_score_comparability(conn)
        scores = load_scores(conn, dimensions)
        conn.close()

    if not contaminated.empty:
        names = set(contaminated["dimension"])
        blocked = names & set(dimensions)
        if blocked and not args.allow_mixed_models:
            print(
                "Refusing to evaluate - these dimensions span multiple models, so any "
                "error metric would partly measure the model switch:\n  "
                + "\n  ".join(
                    f"{r['dimension']}: {r['detail']}"
                    for _, r in contaminated.iterrows()
                    if r["dimension"] in blocked
                )
                + "\n\nRe-score with a single pinned model "
                  "(scripts/run_all_scoring.py --dimension NAME --skip-scored), "
                  "or pass --allow-mixed-models to proceed anyway.",
                file=sys.stderr,
            )
            sys.exit(2)

    if scores.empty:
        print("No scores found for the requested dimension(s).", file=sys.stderr)
        sys.exit(1)

    paired = pair_scores_with_labels(scores, labels)
    if paired.empty:
        print(
            "No overlap between labels and scores - nothing to compare.\n"
            "Check that company/quarter/year/dimension in the CSV match the database.",
            file=sys.stderr,
        )
        sys.exit(1)

    results = evaluate(paired)
    print_report(results)

    if args.json:
        print("\n=== JSON ===")
        print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
