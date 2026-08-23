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

    # Build a complete series for one dimension inside a constrained token
    # budget -- a full 5-dimension sweep costs ~5x as much (BLOCKER-4):
    python scripts/run_all_scoring.py --dimension evasiveness --skip-scored
"""

import sys
import os
import argparse
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import DB_PATH, LOG_PATH, LLM_MODEL_NAME, SCORE_DIMENSIONS
from src.storage.db import init_db, get_chunks
from src.scoring import score_transcript_all
from src.scoring._llm_dimension_scorer import DailyQuotaExhausted
from src.utils.logging import setup_logger


logger = logging.getLogger("earningslens")


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


def get_scored_transcripts(conn, dimensions):
    """(company, quarter, year) that already have every requested dimension scored."""
    placeholders = ",".join("?" * len(dimensions))
    query = f"""
        SELECT company, quarter, year, COUNT(DISTINCT dimension) AS dim_count
        FROM scores
        WHERE dimension IN ({placeholders}) AND company IS NOT NULL
        GROUP BY company, quarter, year
        HAVING dim_count = ?
    """
    cur = conn.cursor()
    cur.execute(query, [*dimensions, len(dimensions)])
    return {(r[0], r[1], r[2]) for r in cur.fetchall()}


def get_scored_on_model(conn, dimensions, model):
    """(company, quarter, year) already scored on `model` for every requested dimension.

    This is what makes a resumed run cheap: re-scoring a transcript that is
    already on the pinned model spends tokens to produce the identical number.
    """
    placeholders = ",".join("?" * len(dimensions))
    query = f"""
        SELECT company, quarter, year, COUNT(DISTINCT dimension) AS dim_count
        FROM scores
        WHERE dimension IN ({placeholders}) AND model_name = ? AND company IS NOT NULL
        GROUP BY company, quarter, year
        HAVING dim_count = ?
    """
    cur = conn.cursor()
    cur.execute(query, [*dimensions, model, len(dimensions)])
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
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip transcripts that already have every requested dimension scored, by any model")
    parser.add_argument("--skip-scored", action="store_true",
                        help="Skip transcripts already scored ON THE TARGET MODEL for every requested "
                             "dimension. Use this to resume a sweep without re-paying for work already done.")
    parser.add_argument("--model", type=str, help="Override the default LLM model from config")
    parser.add_argument("--dimension", action="append", metavar="NAME",
                        help="Score only this dimension (repeatable). Default: all 5. "
                             "Narrowing is how a complete single-dimension series fits in a daily token budget.")
    args = parser.parse_args()

    dimensions = args.dimension or list(SCORE_DIMENSIONS)
    unknown = [d for d in dimensions if d not in SCORE_DIMENSIONS]
    if unknown:
        parser.error(f"unknown dimension(s): {', '.join(unknown)}. Choose from: {', '.join(SCORE_DIMENSIONS)}")

    setup_logger(LOG_PATH)
    conn = init_db(str(DB_PATH))

    company_filter = args.company.upper() if args.company else None
    transcripts = get_unique_transcripts(conn, company_filter)

    if args.year:
        transcripts = [(c, q, y) for c, q, y in transcripts if y == args.year]

    model = args.model or LLM_MODEL_NAME or "unknown"

    if args.skip_existing:
        scored = get_scored_transcripts(conn, dimensions)
        before = len(transcripts)
        transcripts = [(c, q, y) for c, q, y in transcripts if (c, q, y) not in scored]
        if before - len(transcripts):
            logger.info("Skipping %d transcript(s) already scored by any model.", before - len(transcripts))

    if args.skip_scored:
        scored = get_scored_on_model(conn, dimensions, model)
        before = len(transcripts)
        transcripts = [(c, q, y) for c, q, y in transcripts if (c, q, y) not in scored]
        if before - len(transcripts):
            logger.info("Skipping %d transcript(s) already scored on %s.", before - len(transcripts), model)

    if not transcripts:
        logger.warning("No transcripts found in the database.")
        conn.close()
        return

    logger.info("Found %d transcript(s) to score.", len(transcripts))
    for company, quarter, year in transcripts:
        logger.info("  - %s %s %s", company, quarter, year)

    if args.dry_run:
        print("\n[DRY RUN] The following transcripts would be scored:")
        for company, quarter, year in transcripts:
            transcript_id, chunk_texts = assemble_chunks(conn, company, quarter, year)
            print(f"  {company} {quarter} {year} -- {len(chunk_texts)} chunks, transcript_id={transcript_id}")
        print(f"\nDimensions: {', '.join(dimensions)}")
        print(f"Model: {model}")
        planned = len(transcripts) * len(dimensions)
        print(f"Dimension-scores to produce: {planned}")
        # ~20k tokens per dimension-score, measured; free tier caps at 200k/day.
        est = planned * 20_000
        print(f"Estimated tokens: ~{est:,} ({est / 200_000:.1f} days of free-tier budget)")
        conn.close()
        return

    success_count = 0
    fail_count = 0
    quota_exhausted = False

    for i, (company, quarter, year) in enumerate(transcripts, 1):
        logger.info("[%d/%d] Scoring %s %s %s ...", i, len(transcripts), company, quarter, year)

        transcript_id, chunk_texts = assemble_chunks(conn, company, quarter, year)
        if transcript_id is None or not chunk_texts:
            logger.warning("  No chunks found for %s %s %s -- skipping.", company, quarter, year)
            fail_count += 1
            continue

        try:
            results = score_transcript_all(
                conn, transcript_id, chunk_texts, model=args.model, dimensions=dimensions
            )
        except DailyQuotaExhausted as e:
            quota_exhausted = True
            logger.error("%s", e)
            logger.error(
                "Stopped after %d of %d transcript(s). Scores already written are kept; "
                "re-run when the budget resets to continue.",
                i - 1, len(transcripts),
            )
            break

        transcript_success = sum(1 for r in results.values() if r["score"] is not None)

        if transcript_success == len(dimensions):
            success_count += 1
        else:
            fail_count += 1

    logger.info("Scoring complete. %d fully succeeded, %d had failures.", success_count, fail_count)
    print_summary(conn, company_filter)

    # A sweep that scored almost nothing must not look like a success. The
    # previous version exited 0 with '2 fully succeeded, 9 had failures'.
    incomplete = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT company, quarter, year FROM scores
            GROUP BY company, quarter, year HAVING COUNT(DISTINCT dimension) < 5
        )
    """).fetchone()[0]
    conn.close()

    if quota_exhausted:
        print(
            "\nSTOPPED: provider token budget exhausted. "
            f"{incomplete} transcript(s) still incomplete. Re-run to continue.",
            file=sys.stderr,
        )
        sys.exit(3)
    if fail_count:
        print(f"\n{fail_count} transcript(s) did not score all 5 dimensions.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
