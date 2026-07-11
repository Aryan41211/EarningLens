"""
All SQLite schema and CRUD lives here.
This module does ONE thing: persistence. No PDF logic, no cleaning, no chunking.
"""

import sqlite3
from datetime import datetime, timezone


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transcripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            quarter TEXT NOT NULL,
            year INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            chunk_text TEXT NOT NULL,
            word_count INTEGER NOT NULL,
            source_file TEXT NOT NULL,
            extracted_at TEXT NOT NULL,
            UNIQUE(company, quarter, year, chunk_index)
        )
    """)
    conn.commit()
    return conn


def store_transcript(conn, company, quarter, year, chunks, source_file):
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    for idx, chunk in enumerate(chunks):
        cur.execute("""
            INSERT OR REPLACE INTO transcripts
            (company, quarter, year, chunk_index, chunk_text, word_count, source_file, extracted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (company, quarter, year, idx, chunk, len(chunk.split()), source_file, now))
    conn.commit()


def get_chunks(conn, company: str, quarter: str = None, year: int = None):
    """Fetch chunks for a company, optionally filtered by quarter/year."""
    query = "SELECT * FROM transcripts WHERE company = ?"
    params = [company.upper()]
    if quarter:
        query += " AND quarter = ?"
        params.append(quarter)
    if year:
        query += " AND year = ?"
        params.append(year)
    query += " ORDER BY year, quarter, chunk_index"
    cur = conn.cursor()
    cur.execute(query, params)
    return cur.fetchall()
