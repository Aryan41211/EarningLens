"""
Manual inspection script for evasiveness scoring.
Runs scoring against a specified company (all available quarters).
Keyword counts are restricted to Q&A chunks only.
Displays keyword counts, matched phrases, LLM scores, and supporting quotes.

Usage:
    python scripts/run_evasiveness_test.py TCS
    python scripts/run_evasiveness_test.py INFY
"""

import sys
import os
import logging
import time

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


def run_company(conn, company: str) -> None:
    quarters = ["Q1", "Q2", "Q3", "Q4"]

    # ---- LLM run instrumentation totals (for Step 5) ----
    total_llm_calls_attempted = 0  # count when Q&A is detected (LLM invoked)
    total_tokens_used = 0
    total_latency_seconds = 0.0
    token_usage_events_with_total = 0
    llm_failures = 0
    years = sorted(set(
        r[0] for r in conn.cursor().execute(
            "SELECT year FROM transcripts WHERE company = ?", (company.upper(),)
        ).fetchall()
    ))

    if not years:
        print(f"No transcripts found for {company}")
        return

    print("=" * 72)
    print(f"EVASIVENESS SCORING -- {company} (All Quarters)")
    print("=" * 72)

    for year in years:
        for q in quarters:
            chunks = get_chunks(conn, company, q, year)
            if not chunks:
                continue

            chunk_texts = [r[5] for r in chunks]

            qa_idx = find_qa_start_index(chunk_texts)
            qa_texts = chunk_texts[qa_idx:] if qa_idx >= 0 else []
            kw = score_evasiveness_keywords(qa_texts)

            print(f"\n{'-' * 72}")
            print(f"{company} {q} {year}  ({len(chunks)} chunks)")
            print(f"  Q&A boundary: {'chunk ' + str(qa_idx) if qa_idx >= 0 else 'NOT FOUND'}")

            print(f"\n  Keyword Dodge Count (Q&A only): {kw['total_count']}")
            if kw["total_count"] > 0:
                print(f"  Top phrases by frequency:")
                for phrase, count in list(kw["frequency"].items())[:10]:
                    print(f"    {phrase:40s} x{count}")
                print(f"  Matched excerpts (first 5):")
                for m in kw["matched_phrases"][:5]:
                    print(f"    [{m['phrase']}]")
                    print(f"      \"...{m['context']}...\"")

            print(f"\n  --- Full Combined Scoring ---")

            # One LLM call is executed inside score_transcript_evasiveness()
            # when Q&A is detected. Time that call here.
            t0 = time.time()
            full = score_transcript_evasiveness(chunk_texts)
            elapsed = time.time() - t0

            if full["qa_detected"]:
                total_llm_calls_attempted += 1
                llm = full["llm_result"]
                total_latency_seconds += elapsed

                print(f"  LLM call elapsed seconds: {elapsed:.3f}s")

                if llm.get("usage") and llm["usage"].get("total_tokens") is not None:
                    usage = llm["usage"]
                    prompt_tokens = usage.get("prompt_tokens")
                    completion_tokens = usage.get("completion_tokens")
                    total_tokens = usage.get("total_tokens")

                    print(
                        "  LLM usage: "
                        f"prompt_tokens={prompt_tokens}, completion_tokens={completion_tokens}, total_tokens={total_tokens}"
                    )

                    if total_tokens is not None:
                        total_tokens_used += total_tokens
                        token_usage_events_with_total += 1
                else:
                    print("  LLM usage: (not provided by provider/response)")

                if llm.get("evasiveness_score") is not None:
                    print(f"  LLM Evasiveness Score: {llm['evasiveness_score']}/10")
                else:
                    llm_failures += 1
                    print(f"  LLM Evasiveness Score: SKIPPED ({llm.get('error', 'no LLM configured')})")

                if llm.get("supporting_quotes"):
                    print(f"  Supporting Quotes:")
                    for i, quote in enumerate(llm["supporting_quotes"], 1):
                        print(f"    [{i}] \"{quote}\"")
            else:
                print(f"  Q&A section not detected -- LLM scoring skipped.")

    print(f"\n{'=' * 72}")
    print(f"DONE ({company})")

    # ---- Step 5 aggregate totals ----
    print(f"\n  === LLM Totals ({company}) ===")
    print(f"  Total LLM calls attempted (Q&A detected): {total_llm_calls_attempted}")
    print(f"  Total tokens used (sum of usage.total_tokens): {total_tokens_used}")
    print(f"  Token events with total_tokens present: {token_usage_events_with_total}")
    print(f"  Total elapsed latency seconds (sum over attempted calls): {total_latency_seconds:.3f}s")
    if total_llm_calls_attempted > 0:
        print(f"  Avg latency per attempted call: {total_latency_seconds / total_llm_calls_attempted:.3f}s")
    else:
        print("  Avg latency per attempted call: N/A")
    print(f"  Failures/skips (evasiveness_score None for attempted calls): {llm_failures}")

    print(f"{'=' * 72}")


def main():
    company = sys.argv[1] if len(sys.argv) > 1 else "TCS"
    conn = init_db(str(DB_PATH))
    run_company(conn, company)
    conn.close()


if __name__ == "__main__":
    main()