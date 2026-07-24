import sqlite3

DB_PATH = "data/earningslens.db"

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT year, quarter
        FROM transcripts
        WHERE company = ?
        ORDER BY year, quarter
        """,
        ("TCS",),
    )
    rows = cur.fetchall()
    conn.close()

    # Deduplicate (year, quarter)
    seen = set()
    uniq = []
    for y, q in rows:
        key = (y, q)
        if key not in seen:
            seen.add(key)
            uniq.append((y, q))

    for y, q in uniq:
        print(f"{q} {y}")

if __name__ == "__main__":
    main()
