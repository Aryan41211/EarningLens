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
