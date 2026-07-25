"""
Find TCS Q2 2023 LLM response in the log, extract supporting_quotes,
and cross-reference each quote against Q&A chunk indices.

NOTE: This validates LLM-generated supporting_quotes (free-text output)
against the "first 3 + last 2" window. This is DISTINCT from
_validate_chunk_window.py, which validates deterministic DODGE_PHRASES
keyword hits against the same window. Windowing was ultimately rejected
for the scoring pipeline because LLM-generated quotes (like Quote 2 here)
fall outside the window — see CHANGELOG.md for that decision.
"""
import sys
sys.path.insert(0, ".")
import json
from config import DB_PATH
from src.storage.db import init_db, get_chunks
from src.scoring.evasiveness import find_qa_start_index

# Load log data
with open("data/earningslens.log", "r", errors="replace") as f:
    log_text = f.read()

# Find the line containing the LLM raw response JSON for TCS Q2 2023
# Look for the content between "LLM raw response:" and the next log timestamp
entries = log_text.split("LLM raw response: ")
if len(entries) < 2:
    print("ERROR: No 'LLM raw response' entries found in log.")
    sys.exit(1)

# Pick the first entry (TCS Q2 2023)
raw = entries[1]
# The JSON ends at the next newline (log writes the entire response on one line)
json_str = raw.split("\n")[0].strip()

try:
    data = json.loads(json_str)
    score = data.get("evasiveness_score")
    quotes = data.get("supporting_quotes", [])
    print(f"Parsed response: evasiveness_score={score}, {len(quotes)} quote(s)")
    for i, q in enumerate(quotes):
        print(f"  Quote {i+1}: {q[:120]}...")
except json.JSONDecodeError as e:
    print(f"JSON parse error: {e}")
    print(f"First 300 chars of raw: {json_str[:300]}")
    quotes = []

# Now find which Q&A chunk each quote fragment belongs to
conn = init_db(str(DB_PATH))
chunks = get_chunks(conn, "TCS", "Q2", 2023)
chunk_texts = [r[5] for r in chunks]
qa_idx = find_qa_start_index(chunk_texts)
qa_texts = chunk_texts[qa_idx:] if qa_idx >= 0 else []
print(f"\nTotal Q&A chunks: {len(qa_texts)} (transcript chunk index {qa_idx})")
for i, t in enumerate(qa_texts):
    print(f"  qa_texts[{i}] = {len(t.split())} words")

print("\n--- QUOTE LOOKUP ---")
for qi, q in enumerate(quotes):
    # Take first 50 chars of quote as search key
    search = q[:50].strip()
    found = False
    for i, t in enumerate(qa_texts):
        if search in t:
            pos = t.find(search)
            print(f"Quote {qi+1}: FOUND in qa_texts[{i}] at char {pos}")
            print(f"  Key: \"{search}...\"")
            found = True
            break
    if not found:
        # Try just the first 30 chars
        search = q[:40].strip()
        for i, t in enumerate(qa_texts):
            if search in t:
                pos = t.find(search)
                print(f"Quote {qi+1}: FOUND in qa_texts[{i}] at char {pos}")
                print(f"  Key: \"{search}...\"")
                found = True
                break
    if not found:
        # Try word by word
        qwords = q.split()[:5]
        for i, t in enumerate(qa_texts):
            if all(w in t for w in qwords):
                pos = t.find(qwords[0])
                print(f"Quote {qi+1}: FOUND (fuzzy) in qa_texts[{i}] at char {pos}")
                print(f"  Words: {' '.join(qwords)}...")
                found = True
                break
    if not found:
        print(f"Quote {qi+1}: NOT FOUND in any Q&A chunk")
    print()

print("--- WINDOW CHECK ---")
first3 = set(range(0, min(3, len(qa_texts))))
last2 = set(range(max(0, len(qa_texts) - 2), len(qa_texts)))
window = first3 | last2
print(f'  "first 3 + last 2" window indices: {sorted(window)}')
print(f'  Total Q&A chunks: {len(qa_texts)}')

conn.close()
