"""Find TCS Q2 2023 LLM response in the log file and cross-reference against Q&A chunk indices."""
import sys
sys.path.insert(0, ".")
import re
import json
from config import DB_PATH
from src.storage.db import init_db, get_chunks
from src.scoring.evasiveness import find_qa_start_index

# Load log data
with open("data/earningslens.log", "r", errors="replace") as f:
    lines = f.readlines()

# Get the 3 quotes from TCS Q2 2023 LLM runs (log line ~316, 359)
# Find the line containing "We remain committed to our guiding beacon"
target_lines = [l for l in lines if "We remain committed to our guiding beacon" in l and "TCV" in l]
if not target_lines:
    # Try other lines
    target_lines = [l for l in lines if "guiding beacon" in l]

print(f"Found {len(target_lines)} candidate lines with guiding beacon")
for ti, tl in enumerate(target_lines[:3]):
    print(f"Candidate {ti}: {tl[:250]}")

# Extract quotes text from "supporting_quotes": [...] 
# Find the JSON array after "supporting_quotes": 
match = re.search(r'{"evasiveness_score": (\d+), "supporting_quotes": (\[.*?\])}', target_lines[0] if target_lines else "", re.DOTALL)
if match:
    score = match.group(1)
    try:
        quotes = json.loads(match.group(2))
        print(f"\nParsed quotes (score={score}):")
        for i, q in enumerate(quotes):
            print(f"  Quote {i+1}: {q[:120]}...")
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        print(f"Raw match: {match.group(2)[:200]}")
        quotes = []
else:
    print("Could not extract supporting_quotes via regex, trying direct approach")
    # Directly find the line
    for l in lines:
        if '"supporting_quotes"' in l and 'evasiveness_score' in l:
            match = re.search(r'{"evasiveness_score": (\d+), "supporting_quotes": (\[.*?\])}', l, re.DOTALL)
            if match:
                quotes = json.loads(match.group(2))
                break
    else:
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
