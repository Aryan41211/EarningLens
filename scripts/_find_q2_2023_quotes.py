"""Find TCS Q2 2023 LLM response in the log file."""
with open("data/earningslens.log", "r", errors="replace") as f:
    lines = f.readlines()
print(f"Log file: {len(lines)} lines")

# Search for TCS Q2 2023 mentions
for i, l in enumerate(lines):
    if "TCS" in l and "Q2" in l and "2023" in l:
        print(f"[{i}] {l.strip()}")

# Search for any raw LLM response or json containing evasiveness_score
for i, l in enumerate(lines):
    if "raw response" in l.lower() or '{"evasiveness' in l:
        print(f"[{i}] RAW RESPONSE: {l[:500]}")
