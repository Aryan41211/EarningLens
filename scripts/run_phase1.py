"""
Phase 1 entrypoint: PDF -> clean text -> chunks -> SQLite.
This script only orchestrates. All real logic lives in src/.

Usage:
    python scripts/run_phase1.py
    (reads from data/raw_pdfs/, writes to data/earningslens.db)
"""

import argparse
import sys
import os
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import RAW_PDFS_DIR, DB_PATH, CHUNK_TARGET_WORDS, LOG_PATH, MIN_EXTRACTED_WORDS
from src.extraction.pdf_extractor import extract_text_from_pdf, parse_filename_metadata
from src.utils.text_cleaning import clean_extracted_text as clean_text
from src.extraction.chunker import chunk_text
from src.storage.db import init_db, store_transcript
from src.utils.logging import setup_logger
from config import PROCESSED_DIR


logger = logging.getLogger("earningslens")


def validate_extraction(raw_text: str, filename: str) -> bool:
    word_count = len(raw_text.split())
    if word_count < MIN_EXTRACTED_WORDS:
        logger.warning(
            "Extraction too small for %s — %d words (min %d). Skipping.",
            filename, word_count, MIN_EXTRACTED_WORDS,
        )
        return False
    return True


def write_processed_text(pdf_filename: str, cleaned_text: str) -> None:
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    txt_name = os.path.splitext(pdf_filename)[0] + ".txt"
    output_path = os.path.join(PROCESSED_DIR, txt_name)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(cleaned_text)


def main():
    # This script had no argument parsing, so any flag -- including --help --
    # fell straight through to a full re-ingest. Passing --help expecting usage
    # text and getting a rewrite of every chunk row is a genuine footgun.
    parser = argparse.ArgumentParser(
        description="Phase 1: extract PDFs in data/raw_pdfs/ into chunks in SQLite.",
        epilog="Re-running is safe: scores carry their own (company, quarter, year) "
               "and survive the chunk rowid change.",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="List the PDFs that would be processed, then exit")
    args = parser.parse_args()

    setup_logger(LOG_PATH)
    conn = init_db(str(DB_PATH))
    pdf_files = [f for f in os.listdir(RAW_PDFS_DIR) if f.lower().endswith(".pdf")]

    if not pdf_files:
        logger.warning("No PDFs found in %s", RAW_PDFS_DIR)
        return

    if args.dry_run:
        print(f"[DRY RUN] {len(pdf_files)} PDF(s) would be processed:")
        for filename in sorted(pdf_files):
            print(f"  {filename}")
        conn.close()
        return

    logger.info("Found %d PDF(s). Processing...", len(pdf_files))

    for filename in sorted(pdf_files):
        full_path = os.path.join(RAW_PDFS_DIR, filename)
        try:
            company, quarter, year = parse_filename_metadata(filename)
        except ValueError as e:
            logger.warning("Skipped %s: %s", filename, e)
            continue

        logger.info("Processing %s — %s %s %s", filename, company, quarter, year)

        raw_text = extract_text_from_pdf(full_path)
        if not validate_extraction(raw_text, filename):
            continue

        cleaned = clean_text(raw_text)
        write_processed_text(filename, cleaned)
        chunks = chunk_text(cleaned, target_words=CHUNK_TARGET_WORDS)

        if not chunks:
            # A PDF can pass the raw word-count check but lose everything during
            # cleaning (all boilerplate / references / safe-harbor text). Writing
            # zero chunks would DELETE the existing ingest for this
            # (company, quarter, year) and re-insert nothing -- silent data loss,
            # the same class as KNOWN_ISSUES.md HIGH-2. Skip and keep what is there.
            logger.warning(
                "Cleaning produced no chunks for %s %s %s (%s) — "
                "skipping; existing ingest preserved.",
                company, quarter, year, filename,
            )
            continue

        store_transcript(conn, company, quarter, year, chunks, filename)

        logger.info(
            "%s -> %s %s %s (%d chunks, %d words)",
            filename, company, quarter, year,
            len(chunks), len(cleaned.split()),
        )

    conn.close()
    logger.info("Done. Data stored in %s", DB_PATH)


if __name__ == "__main__":
    main()
