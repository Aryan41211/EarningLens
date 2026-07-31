"""
Unified end-to-end scoring runner for all 5 dimensions.

Runs evasiveness, sentiment_shift, complexity_spike, overpromising,
and forward_guidance_vagueness against every transcript in the DB.
Results are persisted to the `scores` table via the orchestrator.

Usage:
    python scripts/run_all_scoring.py                    # score all transcripts
    python scripts/run_all_scoring.py --company TCS      # score only TCS
    python scripts/run_all_scoring.py --company INFY --year 2024
    python scripts/run_all_scoring.py --dry-run          # show what would be scored
    python scripts/run_all_scoring.py --model gpt-4o     # override model
"""

import sys
import os
import argparse
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import DB_PATH, LOG_PATH, LLM_MODEL_NAME, SCORE_DIMENSIONS
from src.storage.db import init_db, get_chunks
from src.scoring import score_transcript_all
from src.utils.logging import setup_logger


logger = logging.getLogger("earningslens")


def get_unique_transcripts(conn, company: str = None):
    """Query unique (company, quarter, year) combinations from the transcripts table."""
    query = "SELECT DISTINCT company, quarter, year FROM transcripts"
    params = []
    if company:
        query += " WHERE company = ?"
        params.append(company.upper())
    query += " ORDER BY company, year, quarter"
    cur = conn.cursor()
    cur.execute(query, params)
    return cur.fetchall()


def assemble_chunks(conn, company: str, quarter: str, year: int) -> tuple[int, list[str]]:
    """Fetch and assemble ordered chunks for a transcript.

    Returns:
        (transcript_id, list_of_chunk_texts)
        transcript_id is the row id of the first chunk (used as the FK for scores).
    """
    rows = get_chunks(conn, company, quarter, year)
    if not rows:
        return None, []
    transcript_id = rows[0][0]
    chunk_texts = [r[5] for r in rows]  # chunk_text is at index 5
    return transcript_id, chunk_texts


def print_summary(conn, company_filter: str = None):
    """Print a summary table of all scores in the DB."""
    query = """
        SELECT t.company, t.quarter, t.year,
               s.dimension, s.score, s.model_name, s.scored_at
        FROM scores s
        JOIN transcripts t ON s.transcript_id = t.id
    """
    params = []
    if company_filter:
        query += " WHERE t.company = ?"
        params.append(company_filter.upper())
    query += " ORDER BY t.company, t.year, t.quarter, s.dimension"

    cur = conn.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()

    if not rows:
        logger.info("No scores found in the database.")
        return

    # Group by transcript
    from collections import defaultdict
    transcripts = defaultdict(dict)
    for company, quarter, year, dimension, score, model, scored_at in rows:
        key = (company, quarter, year)
        transcripts[key][dimension] = score

    # Print table
    dims = SCORE_DIMENSIONS
    header = f"{'Company':<10} {'Quarter':<8} {'Year':<6}" + "".join(f" {d.replace('_', ' ').title():<14}" for d in dims)
    print("\n" + "=" * len(header))
    print("SCORES SUMMARY")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for (company, quarter, year), scores in sorted(transcripts.items()):
        row = f"{company:<10} {quarter:<8} {year:<6}"
        for d in dims:
            val = scores.get(d, "-")
            row += f" {val!s:<14}"
        print(row)

    print("-" * len(header))

    # Averages
    avg_row = f"{'AVERAGE':<10} {'':<8} {'':<6}"
    for d in dims:
        vals = [scores[d] for scores in transcripts.values() if d in scores]
        avg = sum(vals) / len(vals) if vals else 0
        avg_row += f" {avg:<14.1f}"
    print(avg_row)
    print("=" * len(header))

    total_scores = sum(len(v) for v in transcripts.values())
    logger.info("Total scored dimensions: %d across %d transcripts", total_scores, len(transcripts))


def main():
    parser = argparse.ArgumentParser(description="Run all 5 scoring dimensions against transcripts.")
    parser.add_argument("--company", type=str, help="Filter to a specific company (e.g., TCS, INFY)")
    parser.add_argument("--year", type=int, help="Filter to a specific year")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be scored without calling the LLM")
    parser.add_argument("--model", type=str, help="Override the default LLM model from config")
    args = parser.parse_args()

    setup_logger(LOG_PATH)
    conn = init_db(str(DB_PATH))

    company_filter = args.company.upper() if args.company else None
    transcripts = get_unique_transcripts(conn, company_filter)

    if args.year:
        transcripts = [(c, q, y) for c, q, y in transcripts if y == args.year]

    if not transcripts:
        logger.warning("No transcripts found in the database.")
        conn.close()
        return

    model = args.model or LLM_MODEL_NAME or "unknown"

    logger.info("Found %d transcript(s) to score.", len(transcripts))
    for company, quarter, year in transcripts:
        logger.info("  - %s %s %s", company, quarter, year)

    if args.dry_run:
        print("\n[DRY RUN] The following transcripts would be scored:")
        for company, quarter, year in transcripts:
            transcript_id, chunk_texts = assemble_chunks(conn, company, quarter, year)
            print(f"  {company} {quarter} {year} — {len(chunk_texts)} chunks, transcript_id={transcript_id}")
        print(f"\nDimensions: {', '.join(SCORE_DIMENSIONS)}")
        print(f"Model: {model}")
        print(f"Total LLM calls needed: {len(transcripts) * len(SCORE_DIMENSIONS)}")
        conn.close()
        return

    # Run scoring
    success_count = 0
    fail_count = 0

    for i, (company, quarter, year) in enumerate(transcripts, 1):
        logger.info("[%d/%d] Scoring %s %s %s ...", i, len(transcripts), company, quarter, year)

        transcript_id, chunk_texts = assemble_chunks(conn, company, quarter, year)
        if transcript_id is None:
            logger.warning("  No chunks found for %s %s %s — skipping.", company, quarter, year)
            fail_count += 1
            continue

        if not chunk_texts:
            logger.warning("  Empty chunk list for %s %s %s — skipping.", company, quarter, year)
            fail_count += 1
            continue

        try:
            results = score_transcript_all(conn, transcript_id, chunk_texts, model=model)

            # Log per-dimension results
            for dimension, result in results.items():
                llm_result = result.get("llm_result", result)
                score_val = llm_result.get(f"{dimension}_score")
                if score_val is not None:
                    logger.info("  %s: %d/10", dimension, score_val)
                else:
                    error = llm_result.get("error", "no score returned")
                    logger.warning("  %s: FAILED (%s)", dimension, error)

            success_count += 1
        except Exception as e:
            logger.error("  Error scoring %s %s %s: %s", company, quarter, year, e)
            fail_count += 1

    logger.info("Scoring complete. %d succeeded, %d failed.", success_count, fail_count)

    # Print summary
    print_summary(conn, company_filter)

    conn.close()


if __name__ == "__main__":
    main()
