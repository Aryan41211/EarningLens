"""
Analyze TCS Q2 2023 Q&A chunks for boilerplate/redundant patterns
that could be safely stripped before LLM scoring.
"""
import sys
sys.path.insert(0, ".")
import re
from collections import Counter
from config import DB_PATH
from src.storage.db import init_db, get_chunks
from src.scoring.evasiveness import find_qa_start_index

conn = init_db(str(DB_PATH))
chunks = get_chunks(conn, "TCS", "Q2", 2023)
chunk_texts = [r[5] for r in chunks]
qa_idx = find_qa_start_index(chunk_texts)
qa_texts = chunk_texts[qa_idx:] if qa_idx >= 0 else []

print(f"Q&A chunks: {len(qa_texts)}")
print()

# 1. Look for analyst pleasantries / introductions
analyst_patterns = [
    r"(?i)(thank\s+(you|you\s+for\s+(taking|that|the)))[^.]*",
    r"(?i)(my\s+(first|second|next|follow-up)\s+question)[^.]*",
    r"(?i)(i\s+(have|had)\s+a?\s+(couple|few|question))[^.]*",
    r"(?i)(good\s+(morning|afternoon|evening))[^.]*",
    r"(?i)(thanks?\s+(for|a\s+lot|so\s+much))[^.]*",
    r"(?i)(just\s+(one|two)\s+(quick|short)\s+question)[^.]*",
]

# 2. Look for operator / moderator transitions
operator_patterns = [
    r"(?i)(next\s+question\s+(comes|is)\s+from)[^.]*",
    r"(?i)(the\s+next\s+question\s+is\s+from)[^.]*",
    r"(?i)(we\s+have\s+time\s+for\s+one\s+more\s+question)[^.]*",
    r"(?i)(operator:?).*?next.*?question[^.]*",
    r"(?i)(i\s+will\s+now\s+open\s+the\s+floor)[^.]*",
    r"(?i)(ladies\s+and\s+gentlemen)[^.]*",
]

# 3. Look for filler transition phrases
filler_patterns = [
    r"(?i)(so[,.]?\s+(yeah|yes|okay|well|let\s+me|i\s+think))[^.]*",
    r"(?i)(i\s+think\s+what\s+(you're|we\s+are))[^.]*",
    r"(?i)(the\s+way\s+(i|we)\s+(see|look\s+at)\s+it)[^.]*",
    r"(?i)(that's\s+a\s+(great|good|fair)\s+question)[^.]*",
    r"(?i)(that's\s+(right|correct|true|exactly))[^.]*",
]

# Find all matches per chunk
print("=" * 60)
print("1. ANALYST PLEASANTRIES / INTRODUCTIONS")
print("=" * 60)
total_analyst_char_savings = 0
total_analyst_count = 0
for ci, ct in enumerate(qa_texts):
    matches = []
    for p in analyst_patterns:
        for m in re.finditer(p, ct):
            matches.append((m.group(), len(m.group())))
    if matches:
        chars = sum(m[1] for m in matches)
        total_analyst_char_savings += chars
        total_analyst_count += len(matches)
