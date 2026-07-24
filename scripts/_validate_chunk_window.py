"""Fix B validation: verify all 3 supporting quotes fall within 'first 3 + last 2' window."""
import sys, os
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

# Supporting quotes captured from terminal output during TCS Q2 2023 run
quotes = [
    "We remain committed to our guiding beacon, which is the 26% to 28%",
    "We don't see current quarter's TCV as a great big variation",
    "We have not started to give that out",
]
print()
for qi, q in enumerate(quotes):
    print(f"\n--- Quote {qi+1} ---")
    search = q[:50].lower()
    for i, t in enumerate(qa_texts):
        if search in t.lower():
            pos = t.lower().find(search)
            print(f"  Found in qa_texts[{i}] at char {pos}")
            # Show surrounding context
            start = max(0, pos - 20)
            end = min(len(t), pos + len(search) + 20)
            print(f"  Context: ...{t[start:end]}...")

print()
print("--- WINDOW CHECK ---")
first3 = set(range(0, min(3, len(qa_texts))))
last2 = set(range(max(0, len(qa_texts) - 2), len(qa_texts)))
window = first3 | last2
print(f"  \"first 3 + last 2\" window indices: {sorted(window)}")

conn.close()
