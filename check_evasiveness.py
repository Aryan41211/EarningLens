import sqlite3
from config import DB_PATH

conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()

# Query 1: List all evasiveness scores with join
cur.execute("""
    SELECT t.company, t.quarter, t.year
    FROM scores s
    JOIN transcripts t ON s.transcript_id = t.id
    WHERE s.dimension = 'evasiveness'
    ORDER BY t.company, t.year, t.quarter
""")
rows = cur.fetchall()
print("=== EVASIVENESS SCORES ===")
for r in rows:
    print(f"  {r[0]} {r[1]} {r[2]}")
print(f"Total rows: {len(rows)}")
print()

# Query 2: Count
cur.execute("SELECT COUNT(*) FROM scores WHERE dimension = 'evasiveness'")
count = cur.fetchone()[0]
print(f"=== COUNT: {count} ===")
print()

# Also check scoring_runs for evasiveness
cur.execute("""
    SELECT c.company, c.quarter, c.year, COUNT(*)
    FROM scoring_runs s
    JOIN transcripts c ON s.transcript_id = c.id
    GROUP BY c.company, c.quarter, c.year
    ORDER BY c.company, c.year, c.quarter
""")
runs = cur.fetchall()
print("=== SCORING RUNS PER TRANSCRIPT ===")
for r in runs:
    print(f"  {r[0]} {r[1]} {r[2]}: {r[3]} run(s)")

# Also check what transcripts exist
cur.execute("""
    SELECT DISTINCT company, quarter, year FROM transcripts
    ORDER BY company, year, quarter
""")
transcripts = cur.fetchall()
print("\n=== ALL TRANSCRIPTS IN DB ===")
for t in transcripts:
    print(f"  {t[0]} {t[1]} {t[2]}")
print(f"Total transcripts: {len(transcripts)}")

conn.close()