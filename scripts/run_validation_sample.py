"""
Validation script for all 5 scoring dimensions.

Runs one sample transcript through every dimension and displays scores,
supporting quotes, and raw LLM responses for manual human review.

Usage:
    python scripts/run_validation_sample.py                    # first transcript in DB
    python scripts/run_validation_sample.py --company TCS      # specific company
    python scripts/run_validation_sample.py --company INFY --year 2024 --quarter Q3
"""

import sys
import os
import argparse
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import DB_PATH, LOG_PATH, LLM_MODEL_NAME
from src.storage.db import init_db, get_chunks
from src.scoring import DIMENSION_MODULES, SCORE_KEY_MAP
from src.utils.logging import setup_logger

logger = logging.getLogger("earningslens")


def get_sample_transcript(conn, company=None, year=None, quarter=None):
    """Get a single transcript for validation."""
    query = "SELECT DISTINCT company, quarter, year FROM transcripts"
    params = []
    conditions = []
    if company:
        conditions.append("company = ?")
        params.append(company.upper())
    if year:
        conditions.append("year = ?")
        params.append(year)
    if quarter:
        conditions.append("quarter = ?")
        params.append(quarter.upper())
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY company, year, quarter LIMIT 1"
    cur = conn.cursor()
    cur.execute(query, params)
    return cur.fetchone()


def score_all_dimensions(chunks):
    """Score all 5 dimensions on a set of chunks."""
    results = {}
    for dimension in ["evasiveness", "sentiment_shift", "complexity_spike",
                       "overpromising", "forward_guidance_vagueness"]:
        scorer = DIMENSION_MODULES[dimension]
        result = scorer(chunks)
        results[dimension] = result
    return results


def display_results(company, quarter, year, results):
    """Display scores and supporting quotes for all dimensions."""
    print("=" * 72)
    print(f"VALIDATION: {company} {quarter} {year}")
    print(f"Model: {LLM_MODEL_NAME or 'not configured'}")
    print("=" * 72)

    for dimension, result in results.items():
        score_key = SCORE_KEY_MAP[dimension]
        llm = result.get("llm_result", result)
        score = llm.get(score_key)
        quotes = llm.get("supporting_quotes", [])
        error = llm.get("error")

        print(f"\n--- {dimension.replace('_', ' ').title()} ---")

        if error:
            print(f"  Score: ERROR ({error})")
        elif score is not None:
            print(f"  Score: {score}/10")
        else:
            print(f"  Score: not available")

        if quotes:
            print(f"  Supporting quotes:")
            for i, q in enumerate(quotes, 1):
                print(f"    [{i}] \"{q}\"")
        else:
            print(f"  Supporting quotes: (none)")

    print("\n" + "=" * 72)


def main():
    parser = argparse.ArgumentParser(description="Run all 5 dimensions on a sample transcript for validation.")
    parser.add_argument("--company", type=str, help="Filter to a specific company (e.g., TCS, INFY)")
    parser.add_argument("--year", type=int, help="Filter to a specific year")
    parser.add_argument("--quarter", type=str, help="Filter to a specific quarter (e.g., Q1)")
    args = parser.parse_args()

    setup_logger(LOG_PATH)
    conn = init_db(str(DB_PATH))

    sample = get_sample_transcript(conn, args.company, args.year, args.quarter)
    if not sample:
        print("No transcripts found in the database.")
        conn.close()
        return

    company, quarter, year = sample
    chunks = get_chunks(conn, company, quarter, year)
    if not chunks:
        print(f"No chunks found for {company} {quarter} {year}.")
        conn.close()
        return

    chunk_texts = [r[5] for r in chunks]
    print(f"Scoring {company} {quarter} {year} — {len(chunk_texts)} chunks")

    results = score_all_dimensions(chunk_texts)
    display_results(company, quarter, year, results)
    conn.close()


if __name__ == "__main__":
    main()
