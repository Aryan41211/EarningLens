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
        print(f"\nChunk {ci} ({len(ct.split())} words, {len(ct)} chars) — {len(matches)} match(es), ~{chars} chars:")
        for m in matches[:5]:
            print(f"  [{m[1]} chars] \"{m[0][:100]}...\"")

print(f"\nTotal analyst matches across all chunks: {total_analyst_count}")
print(f"Total char savings if stripped: {total_analyst_char_savings}")
print(f"Estimated token savings (~4 chars/token): ~{total_analyst_char_savings // 4}")

print()
print("=" * 60)
print("2. OPERATOR / MODERATOR TRANSITIONS")
print("=" * 60)
total_op_char_savings = 0
total_op_count = 0
for ci, ct in enumerate(qa_texts):
    matches = []
    for p in operator_patterns:
        for m in re.finditer(p, ct):
            matches.append((m.group(), len(m.group())))
    if matches:
        chars = sum(m[1] for m in matches)
        total_op_char_savings += chars
        total_op_count += len(matches)
        print(f"\nChunk {ci}: {len(matches)} match(es), ~{chars} chars:")
        for m in matches[:5]:
            print(f"  [{m[1]} chars] \"{m[0][:120]}...\"")

print(f"\nTotal operator matches: {total_op_count}")
print(f"Total char savings if stripped: {total_op_char_savings}")
print(f"Estimated token savings: ~{total_op_char_savings // 4}")

print()
print("=" * 60)
print("3. FILLER TRANSITION PHRASES")
print("=" * 60)
total_fill_char_savings = 0
total_fill_count = 0
for ci, ct in enumerate(qa_texts):
    matches = []
    for p in filler_patterns:
        for m in re.finditer(p, ct):
            matches.append((m.group(), len(m.group())))
    if matches:
        chars = sum(m[1] for m in matches)
        total_fill_char_savings += chars
        total_fill_count += len(matches)

print(f"Total filler matches: {total_fill_count}")
print(f"Total char savings if stripped: {total_fill_char_savings}")
print(f"Estimated token savings: ~{total_fill_char_savings // 4}")

print()
print("=" * 60)
print("4. COMBINED ESTIMATE")
print("=" * 60)
total_chars = sum(len(ct) for ct in qa_texts)
total_words = sum(len(ct.split()) for ct in qa_texts)
total_savings = total_analyst_char_savings + total_op_char_savings + total_fill_char_savings
print(f"  Total Q&A chars: {total_chars}")
print(f"  Total Q&A words: {total_words}")
print(f"  Estimated tokens (words*1.33): ~{int(total_words * 1.33)}")
print(f"  Strippable chars: {total_savings}")
print(f"  Strippable tokens: ~{total_savings // 4}")
print(f"  % reduction: {total_savings / total_chars * 100:.1f}%")
print(f"  If baseline ~6800 tokens, reduced to: ~{int(6800 * (1 - total_savings / total_chars))}")

print()
print("=" * 60)
print("5. COST-ESTIMATE")
print("=" * 60)
# Cost of running without any reduction
# Assume ~6800 tokens per call, 11 transcripts, 1 dimension
total_tokens = 6800 * 11
# gpt-4.1-mini pricing (approximate): $0.15/1M input, $0.60/1M output
# Assume ~800 output tokens per call
input_cost_per_1m = 0.15
output_cost_per_1m = 0.60
total_input_tokens = total_tokens
total_output_tokens = 800 * 11
print(f"  11 transcripts x 1 dimension:")
print(f"  Total input tokens: ~{total_input_tokens}")
print(f"  Total output tokens: ~{total_output_tokens}")
print(f"  Estimated cost (gpt-4.1-mini): ${total_input_tokens/1_000_000 * input_cost_per_1m + total_output_tokens/1_000_000 * output_cost_per_1m:.4f}")
print(f"  Estimated cost (gpt-4o-mini): ${total_input_tokens/1_000_000 * 0.15 + total_output_tokens/1_000_000 * 0.60:.4f}")
print()
print(f"  At ~15s per call, 11 calls = {11 * 15 // 60}min {11 * 15 % 60}s total latency")
print(f"  Days to complete (if paced): < 1 day")

conn.close()
