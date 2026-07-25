"""
Fix B validation: verify deterministic DODGE_PHRASES keyword hits fall
within the "first 3 + last 2" Q&A chunk window.

import sys
import os
import re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import DB_PATH
from src.storage.db import init_db, get_chunks
from src.scoring.evasiveness import find_qa_start_index, DODGE_PHRASES

conn = init_db(str(DB_PATH))
chunks = get_chunks(conn, "TCS", "Q2", 2023)
chunk_texts = [r[5] for r in chunks]
qa_idx = find_qa_start_index(chunk_texts)
qa_texts = chunk_texts[qa_idx:] if qa_idx >= 0 else []

print("=" * 72)
print("FIX B VALIDATION: TCS Q2 2023")
print("=" * 72)
print(f"Total Q&A chunks: {len(qa_texts)}")
for i, t in enumerate(qa_texts):
    print(f"  qa_texts[{i}] = {len(t.split())} words")

print()
print("--- EVASIVE PHRASES FOUND IN Q&A CHUNKS (from DODGE_PHRASES) ---")
phrase_hits = {}
for i, t in enumerate(qa_texts):
    lower = t.lower()
    hits = []
    for phrase in DODGE_PHRASES:
        pat = re.compile(re.escape(phrase), re.IGNORECASE)
        for m in pat.finditer(lower):
            pos = m.start()
            start_ctx = max(0, pos - 60)
            end_ctx = min(len(t), pos + len(phrase) + 120)
            context = t[start_ctx:end_ctx].replace('\n', ' ').strip()
            hits.append((phrase, context, pos))
            break
    if hits:
        phrase_hits[i] = hits
        for phrase, context, pos in hits:
            print(f'  qa_texts[{i}]: "{phrase}" at char {pos}')
            print(f'    ...{context}...')
            print()

if not phrase_hits:
    print("  (no evasive phrases found in Q&A chunks)")

print()
print("--- WINDOW CHECK ---")
first3 = set(range(0, min(3, len(qa_texts))))
last2 = set(range(max(0, len(qa_texts) - 2), len(qa_texts)))
window = first3 | last2
print(f'  "first 3 + last 2" window indices: {sorted(window)}')
print(f'  Chunks with evasive phrase hits: {sorted(phrase_hits.keys())}')
hits_in_window = sorted([i for i in phrase_hits if i in window])
hits_outside = sorted([i for i in phrase_hits if i not in window])
print(f'  Evasive chunks inside window: {hits_in_window}')
print(f'  Evasive chunks outside window: {hits_outside}')
if hits_outside:
    print(f'  >>> FAIL: {len(hits_outside)} chunk(s) with evasive phrases would be dropped by "first 3 + last 2" <<<')
else:
    print(f'  >>> PASS: all evasive chunks are within the "first 3 + last 2" window <<<')

conn.close()
