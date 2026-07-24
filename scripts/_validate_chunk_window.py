"""Fix B validation: verify all 3 supporting quotes fall within 'first 3 + last 2' window."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import DB_PATH
from src.storage.db import init_db, get_chunks
from src.scoring.evasiveness import find_qa_start_index

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


searches = [
    ("guiding beacon", "Quote 1"),
    ("26%", "Quote 1"),
    ("TCV", "Quote 2"),
    ("great big", "Quote 2"),
    ("have not started", "Quote 3"),
    ("augurs", "Quote 3"),
]

print()
print("--- SEARCHING FOR QUOTE FRAGMENTS ---")
for i, t in enumerate(qa_texts):
    lower = t.lower()
    for term, label in searches:
        if term.lower() in lower:
            pos = lower.find(term.lower())
            print(f'{label}: "{term}" found in qa_texts[{i}] at char {pos}')
            start_ctx = max(0, pos - 30)
            end_ctx = min(len(t), pos + len(term) + 80)
            print(f'  Context: ...{t[start_ctx:end_ctx]}...')
            print()

print("--- WINDOW CHECK ---")
first3 = set(range(0, min(3, len(qa_texts))))
last2 = set(range(max(0, len(qa_texts) - 2), len(qa_texts)))
window = first3 | last2
print(f'  "first 3 + last 2" window indices: {sorted(window)}')

