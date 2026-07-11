"""
Phase 1 entrypoint: PDF -> clean text -> chunks -> SQLite.
This script only orchestrates. All real logic lives in src/.

Usage:
    python scripts/run_phase1.py
    (reads from data/raw_pdfs/, writes to data/earningslens.db)
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import RAW_PDFS_DIR, DB_PATH, CHUNK_TARGET_WORDS
from src.extraction.pdf_extractor import extract_text_from_pdf, parse_filename_metadata
from src.extraction.cleaner import clean_text
from src.extraction.chunker import chunk_text
from src.storage.db import init_db, store_transcript
from config import PROCESSED_DIR


def write_processed_text(pdf_filename: str, cleaned_text: str) -> None:
    """Persist cleaned transcript text for manual inspection/debugging."""
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    txt_name = os.path.splitext(pdf_filename)[0] + ".txt"
    output_path = os.path.join(PROCESSED_DIR, txt_name)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(cleaned_text)


def main():
    conn = init_db(str(DB_PATH))
    pdf_files = [f for f in os.listdir(RAW_PDFS_DIR) if f.lower().endswith(".pdf")]

    if not pdf_files:
        print(f"No PDFs found in {RAW_PDFS_DIR}. Add your downloaded transcripts there first.")
        return

    print(f"Found {len(pdf_files)} PDF(s). Processing...\n")

    for filename in pdf_files:
        full_path = os.path.join(RAW_PDFS_DIR, filename)
        try:
            company, quarter, year = parse_filename_metadata(filename)
        except ValueError as e:
            print(f"  [SKIPPED] {filename}: {e}")
            continue

        raw_text = extract_text_from_pdf(full_path)
        cleaned = clean_text(raw_text)
        write_processed_text(filename, cleaned)
        chunks = chunk_text(cleaned, target_words=CHUNK_TARGET_WORDS)

        store_transcript(conn, company, quarter, year, chunks, filename)

        print(
            f"  [OK] {filename} -> {company} {quarter} {year} "
            f"({len(chunks)} chunks, {len(cleaned.split())} words, processed txt saved)"
        )

    conn.close()
    print(f"\nDone. Data stored in {DB_PATH}")


if __name__ == "__main__":
    main()
