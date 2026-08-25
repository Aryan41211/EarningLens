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

from config import DB_PATH, LLM_MODEL_NAME, LOG_PATH, NOTEBOOKS_DIR, SCORE_DIMENSIONS
from src.storage.db import init_db
from src.evaluation import TARGETS, evaluate, meets_target, pair_scores_with_labels
from src.trends.metrics import check_score_comparability
from src.utils.logging import setup_logger

logger = logging.getLogger("earningslens")

DEFAULT_LABELS = NOTEBOOKS_DIR / "labels.csv"


def load_scores(
    conn,
    dimensions: list[str],
    prompt_version: str | None = None,
    model_name: str | None = None,
) -> pd.DataFrame:
    placeholders = ",".join("?" * len(dimensions))
    sql = f"""
        SELECT company, quarter, year, dimension, score, model_name, prompt_version
        FROM scores
        WHERE dimension IN ({placeholders}) AND company IS NOT NULL
    """
    params: list = list(dimensions)
    if prompt_version:
        sql += " AND prompt_version = ?"
        params.append(prompt_version)
    if model_name:
        sql += " AND model_name = ?"
        params.append(model_name)
    return pd.read_sql_query(sql, conn, params=params)


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


def print_comparison(
    per_version: dict[str, dict],
    dimension: str,
    model: str | None = None,
    dropped: dict[str, int] | None = None,
) -> None:
    """Two prompt versions, same labels, side by side.

    This is EVALUATION.md section 1.5 option 3, and it carries that section's
    condition with it: the 11 labels informed evasiveness-v2's design, so a v2
    number measured on them is in-sample. The banner is not optional decoration
    -- an unlabelled improvement here is exactly the kind of claim this project
    has already had to retract once.
    """
    versions = list(per_version)
    print("\n" + "=" * 78)
    print(f"PROMPT COMPARISON - {dimension}")
    print("=" * 78)
    if model:
        print(f"Model held constant: {model}")
    print("IN-SAMPLE. These labels informed the revised prompt's design, so any")
    print("improvement below is an upper bound, not an out-of-sample result.")
    print("Quote it as in-sample every time. See EVALUATION.md section 1.5.")

    header = f"\n  {'metric':<24}" + "".join(f"{v:>22}" for v in versions)
    print(header)
    print("  " + "-" * (24 + 22 * len(versions)))

    for metric, label in (
        ("mae", "MAE (lower better)"),
        ("spearman", "Spearman (higher)"),
        ("within_2", "Within 2 (higher)"),
        ("directional_agreement", "Direction (higher)"),
    ):
        row = f"  {label:<24}"
        for version in versions:
            row += f"{_fmt(per_version[version].get(metric), metric):>22}"
        print(row)

    row = f"  {'n pairs':<24}"
    for version in versions:
        row += f"{per_version[version]['n']:>22}"
    print(row)

    if len(versions) == 2:
        a, b = versions
        deltas = []
        for metric, better_is_lower in (
            ("mae", True), ("spearman", False),
            ("within_2", False), ("directional_agreement", False),
        ):
            first, second = per_version[a].get(metric), per_version[b].get(metric)
            if first is None or second is None:
                continue
            change = second - first
            improved = change < 0 if better_is_lower else change > 0
            deltas.append((metric, change, improved))
        if deltas:
            print(f"\n  {b} vs {a}:")
            for metric, change, improved in deltas:
                verdict = "better" if improved else ("same" if change == 0 else "worse")
                print(f"    {metric:<24} {change:+.2f}  {verdict}")

    n_common = per_version[versions[0]]["n"]
    if dropped and any(dropped.values()):
        print("\n  Restricted to the transcripts every version covers, so the columns are")
        print("  comparable. Excluded as not scored under all versions:")
        for version, count in dropped.items():
            if count:
                print(f"    {version}: {count} transcript(s)")

    if n_common < 5:
        print(f"\n  WARNING: only {n_common} transcript(s) scored under every version.")
        print("  Too few to conclude anything. Finish the sweep before quoting this.")

    print("=" * 78)


def main():
    parser = argparse.ArgumentParser(description="Evaluate LLM scores against human labels.")
    parser.add_argument("--labels", default=str(DEFAULT_LABELS),
                        help=f"CSV of human labels (default: {DEFAULT_LABELS})")
    parser.add_argument("--dimension", action="append", metavar="NAME",
                        help="Evaluate only this dimension (repeatable). Default: all.")
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--json", action="store_true", help="Also emit results as JSON")
    parser.add_argument("--prompt-version", metavar="VERSION",
                        help="Evaluate only scores from this prompt version, e.g. "
                             "evasiveness-v2. Required to compare prompt revisions, since a "
                             "transcript can hold several variants.")
    parser.add_argument("--against", choices=["db", "reviewed"], default="db",
                        help="'db' compares the current scores table. 'reviewed' compares the "
                             "llm_score_at_review column in the labels file -- the scores the "
                             "human actually saw, which stays a clean single-model comparison "
                             "even after the database has been re-scored by other models.")
    parser.add_argument("--model", metavar="NAME",
                        help="Evaluate only scores from this model. Also the model held "
                             "constant by --compare, where it defaults to the configured "
                             "LLM_MODEL_NAME.")
    parser.add_argument("--compare", action="append", metavar="VERSION",
                        help="Evaluate two prompt versions side by side against the same "
                             "labels, e.g. --compare evasiveness-v1 --compare evasiveness-v2. "
                             "Reported as in-sample: the labels informed v2's design "
                             "(EVALUATION.md section 1.5).")
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

    if args.compare:
        if len(args.compare) < 2:
            parser.error("--compare needs at least two versions to compare")
        if len(dimensions) != 1:
            parser.error("--compare works on one dimension at a time; pass --dimension NAME")
        dimension = dimensions[0]

        # A prompt comparison only isolates the prompt if the model is held
        # constant. evasiveness-v1 spans three models, so without this the "v1"
        # column would measure the model mix and the delta would be unreadable.
        compare_model = args.model or LLM_MODEL_NAME
        if not compare_model:
            parser.error("--compare needs a model to hold constant; pass --model")

        conn = init_db(args.db)
        paired_by_version: dict[str, pd.DataFrame] = {}
        for version in args.compare:
            version_scores = load_scores(conn, [dimension], version, compare_model)
            if version_scores.empty:
                print(f"No {version} scores on {compare_model} - score it before comparing.",
                      file=sys.stderr)
                conn.close()
                sys.exit(1)
            version_paired = pair_scores_with_labels(version_scores, labels)
            if version_paired.empty:
                print(f"No labelled overlap for {version}.", file=sys.stderr)
                conn.close()
                sys.exit(1)
            paired_by_version[version] = version_paired
        conn.close()

        # Restrict to the transcripts every version covers. Scoring one prompt on
        # 11 transcripts and the other on 3 and printing the two columns side by
        # side would compare the transcripts, not the prompts.
        def _key(frame: pd.DataFrame) -> set:
            return set(map(tuple, frame[["company", "quarter", "year"]].to_numpy()))

        common = set.intersection(*(_key(f) for f in paired_by_version.values()))
        if not common:
            print(
                f"No transcript has been scored on {compare_model} at every requested "
                "version, so there is nothing to compare like for like.",
                file=sys.stderr,
            )
            sys.exit(1)

        dropped = {v: len(_key(f) - common) for v, f in paired_by_version.items()}
        per_version: dict[str, dict] = {}
        for version, frame in paired_by_version.items():
            keys = frame[["company", "quarter", "year"]].apply(tuple, axis=1)
            per_version[version] = evaluate(frame[keys.isin(common)])[dimension]

        print_comparison(per_version, dimension, model=compare_model, dropped=dropped)
        if args.json:
            print("\n" + json.dumps(per_version, indent=2, default=float))
        return

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
        # Check the slice actually being evaluated, not the whole table: a
        # --model/--prompt-version filter can resolve a mix, and an unfiltered
        # check would refuse a slice that is genuinely clean.
        contaminated = check_score_comparability(
            conn, model=args.model, prompt_version=args.prompt_version
        )
        scores = load_scores(conn, dimensions, args.prompt_version, args.model)
        conn.close()

    if not contaminated.empty:
        names = set(contaminated["dimension"])
        blocked = names & set(dimensions)
        # Do NOT clear `blocked` merely because --prompt-version was passed. A
        # prompt version is not a variant: evasiveness-v1 exists under three
        # different models, so filtering on it alone still leaves a mix -- and
        # the duplicate rows then crashed pair_scores_with_labels with a raw
        # MergeError ("keys are not unique") instead of this explanation.
        # check_score_comparability now receives the same filter, so it already
        # accounts for whatever the caller narrowed to.
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
                  "narrow to one variant with --model NAME (optionally with "
                  "--prompt-version VERSION), or pass --allow-mixed-models to "
                  "proceed anyway.",
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
