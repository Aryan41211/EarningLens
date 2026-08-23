"""CLI to compute and display trend analysis for scored transcripts.

Usage:
    python scripts/run_trends.py                        # All companies
    python scripts/run_trends.py --company TCS          # Single company
    python scripts/run_trends.py --json                 # JSON output
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import DB_PATH, SCORE_DIMENSIONS
from src.storage.db import init_db
from src.trends.metrics import (
    load_scores_from_db,
    compute_qoq_score_change,
    compute_rolling_3q_average,
    compute_trend_label,
    find_biggest_single_quarter_drop,
)


def main():
    parser = argparse.ArgumentParser(description="Compute trend analysis for scored transcripts")
    parser.add_argument("--company", type=str, help="Filter to a specific company")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--db", type=str, default=str(DB_PATH), help="Database path")
    args = parser.parse_args()

    conn = init_db(args.db)
    scores_df = load_scores_from_db(conn)
    conn.close()

    if scores_df.empty:
        print("No scores found in database. Run scoring first.", file=sys.stderr)
        sys.exit(1)

    if args.company:
        scores_df = scores_df[scores_df["company"].str.upper() == args.company.upper()]
        if scores_df.empty:
            print(f"No scores found for {args.company}.", file=sys.stderr)
            sys.exit(1)

    print(f"Loaded {len(scores_df)} transcript(s) with scores.\n")

    # --- QoQ Deltas ---
    qoq = compute_qoq_score_change(scores_df)
    delta_cols = ["company", "quarter", "year"] + [f"{d}_delta" for d in SCORE_DIMENSIONS if f"{d}_delta" in qoq.columns]
    print("=== Quarter-over-Quarter Score Changes ===")
    print(qoq[delta_cols].to_string(index=False))

    # --- Rolling Averages ---
    ma3 = compute_rolling_3q_average(scores_df)
    ma3_cols = ["company", "quarter", "year"] + [f"{d}_ma3" for d in SCORE_DIMENSIONS if f"{d}_ma3" in ma3.columns]
    print("\n=== Rolling 3-Quarter Averages ===")
    print(ma3[ma3_cols].to_string(index=False))

    # --- Trend Labels ---
    trends = compute_trend_label(scores_df)
    trend_cols = ["company", "quarter", "year"] + [f"{d}_trend" for d in SCORE_DIMENSIONS if f"{d}_trend" in trends.columns]
    print("\n=== Trend Labels (IMPROVING / STABLE / DETERIORATING) ===")
    print(trends[trend_cols].to_string(index=False))

    # --- Biggest Drops ---
    drops = find_biggest_single_quarter_drop(scores_df)
    if not drops.empty:
        print("\n=== Biggest Single-Quarter Score Increases (Worsening) ===")
        drop_cols = ["company", "dimension", "prev_year", "prev_quarter", "prev_score", "year", "quarter", "score", "delta"]
        available = [c for c in drop_cols if c in drops.columns]
        print(drops[available].to_string(index=False))
    else:
        print("\nNo quarter-over-quarter changes detected.")

    if args.json:
        output = {
            "qoq_deltas": qoq.to_dict(orient="records"),
            "rolling_averages": ma3.to_dict(orient="records"),
            "trend_labels": trends.to_dict(orient="records"),
            "biggest_drops": drops.to_dict(orient="records") if not drops.empty else [],
        }
        print("\n=== JSON Output ===")
        print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
