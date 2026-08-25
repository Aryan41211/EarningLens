"""Re-score transcripts from stored per-exchange scores, without calling the LLM.

evasiveness-v3 keeps every per-exchange score in `scores.raw_llm_response`
(src/scoring/_exchange_scorer.py explains why). This script reads them back and
recomputes the transcript score under each aggregator in
`src.scoring.evasiveness.AGGREGATORS`, then measures each against the human
labels.

The point is BLOCKER-4. A sweep costs about a day of free-tier budget per
dimension, so the question "which aggregation works best" must be answerable
without paying for it again. Nothing here makes a network call.

READ THE WARNING IT PRINTS. Picking the aggregator that scores best on these
11 labels is selection on the test set. It tells you which aggregations are
*not* worth trying; it cannot certify the winner. See EVALUATION.md section 1.5.

Usage:
    python scripts/compare_aggregators.py
    python scripts/compare_aggregators.py --prompt-version evasiveness-v3
    python scripts/compare_aggregators.py --json
"""

import argparse
import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd

from config import DB_PATH, LOG_PATH, NOTEBOOKS_DIR
from src.evaluation import evaluate, meets_target, pair_scores_with_labels
from src.scoring.evasiveness import AGGREGATORS, DEFAULT_AGGREGATOR, aggregate_exchange_scores
from src.storage.db import init_db
from src.utils.logging import setup_logger

logger = logging.getLogger("earningslens")

DEFAULT_LABELS = NOTEBOOKS_DIR / "labels.csv"


def load_exchange_scores(conn, dimension: str, prompt_version: str, model: str | None):
    """Rows of (company, quarter, year, [per-exchange scores]) for a variant.

    Rows whose raw_llm_response is not the v3 JSON payload are skipped: a v1/v2
    row holds one blended score and has no exchanges to re-aggregate.
    """
    sql = """
        SELECT company, quarter, year, raw_llm_response
        FROM scores
        WHERE dimension = ? AND prompt_version = ? AND company IS NOT NULL
    """
    params: list = [dimension, prompt_version]
    if model:
        sql += " AND model_name = ?"
        params.append(model)

    rows = []
    skipped = 0
    for company, quarter, year, raw in conn.execute(sql, params):
        try:
            payload = json.loads(raw or "")
            scores = [e[f"{dimension}_score"] for e in payload["exchange_scores"]]
        except (ValueError, KeyError, TypeError):
            skipped += 1
            continue
        if scores:
            rows.append((company, quarter, year, scores))
    return rows, skipped


def _fmt(value: float | None, metric: str) -> str:
    if value is None:
        return "     n/a"
    ok = meets_target(metric, value)
    mark = "" if ok is None else (" P" if ok else " F")
    return f"{value:7.2f}{mark}"


def main():
    parser = argparse.ArgumentParser(
        description="Compare aggregators over stored per-exchange scores. Makes no LLM calls."
    )
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--labels", default=str(DEFAULT_LABELS))
    parser.add_argument("--dimension", default="evasiveness")
    parser.add_argument("--prompt-version", default="evasiveness-v3",
                        help="Which stored variant to re-aggregate (must be a per-exchange "
                             "version; v1/v2 rows hold no exchange scores).")
    parser.add_argument("--model", help="Hold one model constant.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    setup_logger(LOG_PATH)

    if not os.path.exists(args.labels):
        print(f"No labels file at {args.labels}.", file=sys.stderr)
        sys.exit(1)
    labels = pd.read_csv(args.labels)

    conn = init_db(args.db)
    rows, skipped = load_exchange_scores(conn, args.dimension, args.prompt_version, args.model)
    conn.close()

    if not rows:
        print(
            f"No stored per-exchange scores for {args.dimension} / {args.prompt_version}"
            + (f" on {args.model}" if args.model else "")
            + ".\nRun the sweep first:\n"
            f"  python scripts/run_all_scoring.py --dimension {args.dimension} "
            f"--prompt-version {args.prompt_version}",
            file=sys.stderr,
        )
        sys.exit(1)

    if skipped:
        print(f"Skipped {skipped} row(s) with no per-exchange scores (v1/v2 rows).")

    exchange_counts = [len(s) for _, _, _, s in rows]
    print(f"\n{len(rows)} transcript(s), {sum(exchange_counts)} scored exchange(s) "
          f"({min(exchange_counts)}-{max(exchange_counts)} per transcript).")

    results: dict[str, dict] = {}
    for method in sorted(AGGREGATORS):
        scored = pd.DataFrame([
            {"company": c, "quarter": q, "year": y, "dimension": args.dimension,
             "score": aggregate_exchange_scores(s, method)}
            for c, q, y, s in rows
        ])
        paired = pair_scores_with_labels(scored, labels)
        if paired.empty:
            continue
        metrics = evaluate(paired)[args.dimension]
        metrics["spread"] = float(scored["score"].max() - scored["score"].min())
        results[method] = metrics

    if not results:
        print("No overlap between the stored scores and the labels.", file=sys.stderr)
        sys.exit(1)

    print("\n" + "=" * 78)
    print(f"AGGREGATOR COMPARISON - {args.dimension} / {args.prompt_version}")
    print("=" * 78)
    print("IN-SAMPLE. Choosing the best row here is selection on the test set:")
    print("these labels cannot then certify the winner. Use it to rule aggregations")
    print("OUT, not to declare one validated. See EVALUATION.md section 1.5.")
    print(f"\n  {'aggregator':<14}{'spread':>8}{'MAE':>10}{'Spearman':>10}"
          f"{'within2':>10}{'direction':>12}")
    print("  " + "-" * 62)
    for method, m in sorted(results.items(), key=lambda kv: -(kv[1]["spearman"] or -9)):
        marker = " *" if method == DEFAULT_AGGREGATOR else "  "
        print(
            f"{marker}{method:<14}{m['spread']:>8.0f}{_fmt(m['mae'], 'mae')}"
            f"{_fmt(m['spearman'], 'spearman')}{_fmt(m['within_2'], 'within_2')}"
            f"{_fmt(m['directional_agreement'], 'directional_agreement'):>12}"
        )
    print(f"\n  * = current default ({DEFAULT_AGGREGATOR}).  P/F = meets the "
          f"EVALUATION.md 3.2 target.")
    print("  'spread' is max score minus min across transcripts. A spread near 0 is")
    print("  the BLOCKER-6 failure: an aggregate that cannot rank anything.")
    print("=" * 78)

    if args.json:
        print("\n" + json.dumps(results, indent=2, default=float))


if __name__ == "__main__":
    main()
