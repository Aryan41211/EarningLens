"""Check current evasiveness scoring status — TCS & INFY."""
import sys, json
sys.path.insert(0, ".")
from config import DB_PATH
import sqlite3

conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()

# Total runs
cur.execute("SELECT COUNT(*) FROM scoring_runs")
total = cur.fetchone()[0]
print(f"=== TOTAL SCORING RUNS: {total} ===\n")

# All distinct company/quarter/year combos that HAVE been scored
cur.execute("""
    SELECT DISTINCT c.company, c.quarter, c.year
    FROM scoring_runs s
    JOIN transcripts c ON s.transcript_id = c.id
    ORDER BY c.company, c.year, c.quarter
""")
scored = set(cur.fetchall())
print(f"Unique company/quarters scored: {len(scored)}")
for s in sorted(scored):
    print(f"  [OK] {s[0]} {s[1]} {s[2]}")
print()

# Load latest score per transcript
cur.execute("""
    SELECT c.company, c.quarter, c.year, s.model_name,
           s.scored_at, s.raw_llm_response
    FROM scoring_runs s
    JOIN transcripts c ON s.transcript_id = c.id
    ORDER BY c.company, c.year, c.quarter, s.scored_at DESC
""")
rows = cur.fetchall()

latest = {}
for r in rows:
    company, quarter, year, model, scored_at, raw = r
    key = f"{company} {quarter} {year}"
    if key not in latest:
        try:
            data = json.loads(raw)
            score = data.get("evasiveness_score", "?")
            quotes = data.get("supporting_quotes", [])
        except:
            score = "?"
            quotes = []
        latest[key] = {"score": score, "model": model, "at": scored_at, "quotes": quotes}

# All transcripts in DB
cur.execute("""
    SELECT DISTINCT company, quarter, year FROM transcripts
    ORDER BY company, year, quarter
""")
all_transcripts = cur.fetchall()
print(f"Total transcripts in DB: {len(all_transcripts)}")
missing = []
for t in all_transcripts:
    key = f"{t[0]} {t[1]} {t[2]}"
    if key not in latest:
        missing.append(key)

if missing:
    print(f"\n[MISSING] scores ({len(missing)}):")
    for m in missing:
        print(f"  {m}")
else:
    print("\n[OK] ALL transcripts scored!")
print()

# Full comparison table
print("=" * 80)
print("FULL SCORING TABLE — All Companies & Quarters")
print("=" * 80)
print(f"{'Company':<8} {'Quarter':<10} {'Score':<8} {'Model':<30} {'Scored At':<25}")
print("-" * 80)
for key in sorted(latest.keys()):
    s = latest[key]
    parts = key.split()
    company, quarter, year = parts[0], parts[1], parts[2]
    print(f"{company:<8} {quarter} {year:<5} {s['score']}/10    {s['model']:<28} {s['at'][:19]:<25}")

print()
print("--- SUPPORTING QUOTES (latest run per transcript) ---")
for key in sorted(latest.keys()):
    s = latest[key]
    print(f"\n{key} (score={s['score']}/10):")
    for i, q in enumerate(s['quotes']):
        print(f"  [{i+1}] {q[:120]}...")

conn.close()
