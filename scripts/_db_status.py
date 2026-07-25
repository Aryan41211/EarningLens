"""Temporary script to check DB status."""
import sys
sys.path.insert(0, ".")
from config import DB_PATH
import sqlite3

conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()

# Get schema
print("=== scoring_runs schema ===")
cur.execute("PRAGMA table_info(scoring_runs)")
for col in cur.fetchall():
    print(col)

print()

print("=== transcripts schema ===")
cur.execute("PRAGMA table_info(transcripts)")
for col in cur.fetchall():
    print(col)

print()

# Check scoring_runs table
cur.execute("SELECT COUNT(*) FROM scoring_runs")
total = cur.fetchone()[0]
print(f"=== TOTAL SCORING RUNS: {total} ===")
print()

# List all runs
cur.execute("""
    SELECT c.company, c.quarter, c.year, s.transcript_id,
           s.scored_at, s.raw_response
    FROM scoring_runs s
    JOIN transcripts c ON s.transcript_id = c.id
    ORDER BY c.company, c.year, c.quarter
""")
rows = cur.fetchall()
for r in rows:
    company, quarter, year, tid, scored_at, raw = r
    score_str = "?"
    try:
        import json
        data = json.loads(raw)
        score_str = str(data.get("evasiveness_score", "?"))
    except:
        pass
    print(f"{company} {quarter} {year} (tid={tid}) | score={score_str} | at={scored_at}")

conn.close()
