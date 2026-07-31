"""
Unified end-to-end scoring runner for all 5 dimensions.

Runs evasiveness, sentiment_shift, complexity_spike, overpromising,
and forward_guidance_vagueness against every transcript in the DB.
Results are persisted to the scores table.

Handles token limits by windowing chunks for non-evasiveness dimensions
(evasiveness already restricts to Q&A-only chunks internally).

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
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import DB_PATH, LOG_PATH, LLM_MODEL_NAME, SCORE_DIMENSIONS
from src.storage.db import init_db, get_chunks, store_score
from src.scoring.evasiveness import score_transcript_evasiveness
from src.scoring.sentiment_shift import score_sentiment_shift_llm
from src.scoring.complexity_spike import score_complexity_spike_llm
from src.scoring.overpromising import score_overpromising_llm
from src.scoring.forward_guidance_vagueness import score_forward_guidance_vagueness_llm
from src.utils.logging import setup_logger


logger = logging.getLogger("earningslens")

CHUNKS_PER_WINDOW = 5
MAX_RETRIES = 3
RETRY_BASE_DELAY = 60  # seconds — start with 60s for daily limits


def is_rate_limit_error(exc):
    return "429" in str(exc) or "rate_limit_exceeded" in str(exc)


def retry_on_rate_limit(fn, *args, **kwargs):
    """Call fn with retries on 429 rate limit errors, using exponential backoff."""
    for attempt in range(MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if is_rate_limit_error(e) and attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning("    Rate limited (attempt %d/%d). Waiting %ds...", attempt + 1, MAX_RETRIES, delay)
                time.sleep(delay)
            else:
                raise

DIMENSION_SCORERS = {
    "evasiveness": score_transcript_evasiveness,
    "sentiment_shift": score_sentiment_shift_llm,
    "complexity_spike": score_complexity_spike_llm,
    "overpromising": score_overpromising_llm,
    "forward_guidance_vagueness": score_forward_guidance_vagueness_llm,
}

SCORE_KEY_MAP = {
    "evasiveness": "evasiveness_score",
    "sentiment_shift": "sentiment_shift_score",
    "complexity_spike": "complexity_spike_score",
    "overpromising": "overpromising_score",
    "forward_guidance_vagueness": "forward_guidance_vagueness_score",
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


def score_with_windowing(scorer_fn, chunks, dimension, window_size=CHUNKS_PER_WINDOW):
    if not chunks:
        return {"score": None, "supporting_quotes": [], "raw_response": "", "error": "No chunks"}

    if len(chunks) <= window_size:
        return retry_on_rate_limit(scorer_fn, chunks)

    scores = []
    all_quotes = []
    all_raw = []

    step = max(1, window_size // 2)
    for start in range(0, len(chunks), step):
        window = chunks[start:start + window_size]
        if len(window) < 2:
            break

        logger.info("      Window chunks %d-%d of %d", start, start + len(window), len(chunks))
        result = retry_on_rate_limit(scorer_fn, window)
        score_key = SCORE_KEY_MAP[dimension]
        score_val = result.get(score_key)
        if score_val is not None:
            scores.append(score_val)
        if "supporting_quotes" in result:
            all_quotes.extend(result["supporting_quotes"])
        if "raw_response" in result:
            all_raw.append(result["raw_response"])

    if not scores:
        return scorer_fn(chunks[-window_size:])

    avg_score = round(sum(scores) / len(scores))
    return {
        "score": avg_score,
        "supporting_quotes": all_quotes[:3],
        "raw_response": "\n---window---\n".join(all_raw),
    }


def score_dimension(conn, transcript_id, dimension, chunks, model):
    scorer = DIMENSION_SCORERS[dimension]
    score_key = SCORE_KEY_MAP[dimension]

    if dimension == "evasiveness":
        result = retry_on_rate_limit(scorer, chunks)
        llm_result = result.get("llm_result", result)
        score_value = llm_result.get(score_key)
        quotes = llm_result.get("supporting_quotes", [])
        raw = llm_result.get("raw_response", "")
    else:
        result = score_with_windowing(scorer, chunks, dimension)
        score_value = result.get("score") or result.get(score_key)
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
        print(f"Total LLM calls needed: ~{len(transcripts) * len(SCORE_DIMENSIONS)} (windowing may add more)")
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
