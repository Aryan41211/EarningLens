"""
Manual inspection script for evasiveness scoring.
Runs scoring against TCS (all available quarters).
Displays keyword counts, matched phrases, LLM scores, and supporting quotes.
"""

import sys
import os
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import DB_PATH, LOG_PATH
from src.storage.db import init_db, get_chunks
from src.scoring.evasiveness import (
    score_transcript_evasiveness,
    score_evasiveness_keywords,
    find_qa_start_index,
)
from src.utils.logging import setup_logger


setup_logger(LOG_PATH)


def main():
    conn = init_db(str(DB_PATH))
    quarters = ["Q1", "Q2", "Q3", "Q4"]
    years = sorted(set(
        r[0] for r in conn.cursor().execute(
            "SELECT year FROM transcripts WHERE company='TCS'"
        ).fetchall()
    ))

    print("=" * 72)
    print("EVASIVENESS SCORING -- TCS (All Quarters)")
    print("=" * 72)

    for year in years:
        for q in quarters:
            chunks = get_chunks(conn, "TCS", q, year)
            if not chunks:
                continue

            chunk_texts = [r[5] for r in chunks]

            # Keyword-only scan
            kw = score_evasiveness_keywords(chunk_texts)
            qa_idx = find_qa_start_index(chunk_texts)

            print(f"\n{'-' * 72}")
            print(f"TCS {q} {year}  ({len(chunks)} chunks)")
            print(f"  Q&A boundary: {'chunk ' + str(qa_idx) if qa_idx >= 0 else 'NOT FOUND'}")

            # Keyword results
            print(f"\n  Keyword Dodge Count: {kw['total_count']}")
            if kw["total_count"] > 0:
                print(f"  Top phrases by frequency:")
                for phrase, count in list(kw["frequency"].items())[:10]:
                    print(f"    {phrase:40s} x{count}")
                print(f"  Matched excerpts (first 5):")
                for m in kw["matched_phrases"][:5]:
                    print(f"    [{m['phrase']}]")
                    print(f"      \"...{m['context']}...\"")

            # Full combined scoring (keyword + LLM if configured)
            print(f"\n  --- Full Combined Scoring ---")
            full = score_transcript_evasiveness(chunk_texts)

            if full["qa_detected"]:
                llm = full["llm_result"]
                if llm.get("evasiveness_score") is not None:
                    print(f"  LLM Evasiveness Score: {llm['evasiveness_score']}/10")
                else:
                    print(f"  LLM Evasiveness Score: SKIPPED ({llm.get('error', 'no LLM configured')})")

                if llm.get("supporting_quotes"):
                    print(f"  Supporting Quotes:")
                    for i, quote in enumerate(llm["supporting_quotes"], 1):
                        print(f"    [{i}] \"{quote}\"")
            else:
                print(f"  Q&A section not detected — LLM scoring skipped.")

    conn.close()
    print(f"\n{'=' * 72}")
    print("DONE")
    print(f"{'=' * 72}")


if __name__ == "__main__":
    main()