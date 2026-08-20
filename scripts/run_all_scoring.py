"""
Unified end-to-end scoring runner for all 5 dimensions.

Runs evasiveness, sentiment_shift, complexity_spike, overpromising,
and forward_guidance_vagueness against every transcript in the DB.
Results are persisted to the scores table.

Every transcript is processed as a single complete document.
No chunk windowing, no positional selection, no truncation.

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
from src.storage.db import init_db, get_chunks, store_score
from src.scoring.evasiveness import score_transcript_evasiveness
from src.scoring.sentiment_shift import score_sentiment_shift_llm
from src.scoring.complexity_spike import score_complexity_spike_llm
from src.scoring.overpromising import score_overpromising_llm
from src.scoring.forward_guidance_vagueness import score_forward_guidance_vagueness_llm
from src.scoring import SCORE_KEY_MAP
from src.utils.logging import setup_logger


logger = logging.getLogger("earningslens")

DIMENSION_SCORERS = {
    "evasiveness": score_transcript_evasiveness,
    "sentiment_shift": score_sentiment_shift_llm,
    "complexity_spike": score_complexity_spike_llm,
    "overpromising": score_overpromising_llm,
    "forward_guidance_vagueness": score_forward_guidance_vagueness_llm,
}


def get_unique_transcripts(conn, company=None):
    query = "SELECT DISTINCT company, quarter, year FROM transcripts"
    params = []
    if company:
        query += " WHERE company = ?"
        params.append(company.upper())
    query += " ORDER BY company, year, quarter"
    cur = conn.cursor()
    cur.execute(query, params)
    return cur.fetchall()


def assemble_chunks(conn, company, quarter, year):
    rows = get_chunks(conn, company, quarter, year)
    if not rows:
        return None, []
    transcript_id = rows[0][0]
    chunk_texts = [r[5] for r in rows]
    return transcript_id, chunk_texts


def score_dimension(conn, transcript_id, dimension, chunks, model):
    """Score a single dimension for a transcript. Sends all chunks as a complete document."""
    scorer = DIMENSION_SCORERS[dimension]
    score_key = SCORE_KEY_MAP[dimension]

    if dimension == "evasiveness":
        result = scorer(chunks, model=model)
        llm_result = result.get("llm_result", result)
        score_value = llm_result.get(score_key)
        quotes = llm_result.get("supporting_quotes", [])
        raw = llm_result.get("raw_response", "")
    else:
        result = scorer(chunks, model=model)
        score_value = result.get(score_key)
        quotes = result.get("supporting_quotes", [])
        raw = result.get("raw_response", "")

    if score_value is not None:
        store_score(
            conn, transcript_id, dimension, score_value,
            quotes, model, f"{dimension}-v1", raw,
        )
        logger.info("    %s: %d/10", dimension, score_value)
        return True
    else:
        error_msg = "unknown"
        if isinstance(result, dict):
            error_msg = result.get("error") or result.get("llm_result", {}).get("error", "no score returned")
        logger.warning("    %s: FAILED (%s)", dimension, error_msg)
        return False


def get_scored_transcripts(conn):
    """Return set of (company, quarter, year) that already have all 5 dimensions scored."""
    query = """
        SELECT t.company, t.quarter, t.year, COUNT(DISTINCT s.dimension) as dim_count
        FROM transcripts t
        JOIN scores s ON s.transcript_id = t.id
        GROUP BY t.company, t.quarter, t.year
        HAVING dim_count = 5
    """
    cur = conn.cursor()
    cur.execute(query)
    return {(r[0], r[1], r[2]) for r in cur.fetchall()}


def print_summary(conn, company_filter=None):
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

    from collections import defaultdict
    transcripts = defaultdict(dict)
    for company, quarter, year, dimension, score, model, scored_at in rows:
        key = (company, quarter, year)
        transcripts[key][dimension] = score

    dims = SCORE_DIMENSIONS
    col_w = 16
    header = f"{'Company':<10} {'Quarter':<8} {'Year':<6}" + "".join(f" {d.replace('_',' ').title():<{col_w}}" for d in dims)
    print("\n" + "=" * len(header))
    print("SCORES SUMMARY")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for (company, quarter, year), scores in sorted(transcripts.items()):
        row = f"{company:<10} {quarter:<8} {year:<6}"
        for d in dims:
            val = scores.get(d, "-")
            row += f" {val!s:<{col_w}}"
        print(row)

    print("-" * len(header))

    avg_row = f"{'AVERAGE':<10} {'':<8} {'':<6}"
    for d in dims:
        vals = [scores[d] for scores in transcripts.values() if d in scores]
        avg = sum(vals) / len(vals) if vals else 0
        avg_row += f" {avg:<{col_w}.1f}"
    print(avg_row)
    print("=" * len(header))

    total_scores = sum(len(v) for v in transcripts.values())
    logger.info("Total scored dimensions: %d across %d transcripts", total_scores, len(transcripts))


def main():
    parser = argparse.ArgumentParser(description="Run all 5 scoring dimensions against transcripts.")
    parser.add_argument("--company", type=str, help="Filter to a specific company (e.g., TCS, INFY)")
    parser.add_argument("--year", type=int, help="Filter to a specific year")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be scored without calling the LLM")
    parser.add_argument("--skip-existing", action="store_true", help="Skip transcripts that already have all 5 scores")
    parser.add_argument("--model", type=str, help="Override the default LLM model from config")
    args = parser.parse_args()

    setup_logger(LOG_PATH)
    conn = init_db(str(DB_PATH))

    company_filter = args.company.upper() if args.company else None
    transcripts = get_unique_transcripts(conn, company_filter)

    if args.year:
        transcripts = [(c, q, y) for c, q, y in transcripts if y == args.year]

    if args.skip_existing:
        scored = get_scored_transcripts(conn)
        before = len(transcripts)
        transcripts = [(c, q, y) for c, q, y in transcripts if (c, q, y) not in scored]
        skipped = before - len(transcripts)
        if skipped:
            logger.info("Skipping %d already-scored transcript(s).", skipped)

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
            print(f"  {company} {quarter} {year} -- {len(chunk_texts)} chunks, transcript_id={transcript_id}")
        print(f"\nDimensions: {', '.join(SCORE_DIMENSIONS)}")
        print(f"Model: {model}")
        print(f"Total LLM calls needed: {len(transcripts) * len(SCORE_DIMENSIONS)}")
        conn.close()
        return

    success_count = 0
    fail_count = 0

    for i, (company, quarter, year) in enumerate(transcripts, 1):
        logger.info("[%d/%d] Scoring %s %s %s ...", i, len(transcripts), company, quarter, year)

        transcript_id, chunk_texts = assemble_chunks(conn, company, quarter, year)
        if transcript_id is None or not chunk_texts:
            logger.warning("  No chunks found for %s %s %s -- skipping.", company, quarter, year)
            fail_count += 1
            continue

        transcript_success = 0
        for dimension in SCORE_DIMENSIONS:
            try:
                ok = score_dimension(conn, transcript_id, dimension, chunk_texts, model)
                if ok:
                    transcript_success += 1
            except Exception as e:
                logger.error("    %s error: %s", dimension, e)

        if transcript_success == len(SCORE_DIMENSIONS):
            success_count += 1
        else:
            fail_count += 1

    logger.info("Scoring complete. %d fully succeeded, %d had failures.", success_count, fail_count)
    print_summary(conn, company_filter)
    conn.close()


if __name__ == "__main__":
    main()
