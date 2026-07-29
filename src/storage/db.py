"""
All SQLite schema and CRUD lives here.
This module does ONE thing: persistence. No PDF logic, no cleaning, no chunking.
"""

import json
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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scoring_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transcript_id INTEGER NOT NULL,
            model_name TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            scored_at TEXT NOT NULL,
            raw_llm_response TEXT NOT NULL,
            FOREIGN KEY (transcript_id) REFERENCES transcripts(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transcript_id INTEGER NOT NULL,
            dimension TEXT NOT NULL,
            score INTEGER NOT NULL,
            supporting_quotes TEXT,
            scored_at TEXT NOT NULL,
            model_name TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            raw_llm_response TEXT NOT NULL,
            FOREIGN KEY (transcript_id) REFERENCES transcripts(id),
            UNIQUE(transcript_id, dimension)
        )
    """)
    conn.commit()
    return conn


def store_transcript(conn, company, quarter, year, chunks, source_file):
    cur = conn.cursor()
    # Delete any existing chunks for this transcript to avoid stale high-index chunks
    cur.execute("""
        DELETE FROM transcripts WHERE company = ? AND quarter = ? AND year = ?
    """, (company, quarter, year))
    now = datetime.now(timezone.utc).isoformat()
    for idx, chunk in enumerate(chunks):
        cur.execute("""
            INSERT INTO transcripts
            (company, quarter, year, chunk_index, chunk_text, word_count, source_file, extracted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (company, quarter, year, idx, chunk, len(chunk.split()), source_file, now))
    conn.commit()


def store_scoring_run(conn, transcript_id, model_name, prompt_version, raw_response):
    """Persist a scoring run with the raw LLM response for auditability."""
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    cur.execute("""
        INSERT INTO scoring_runs
        (transcript_id, model_name, prompt_version, scored_at, raw_llm_response)
        VALUES (?, ?, ?, ?, ?)
    """, (transcript_id, model_name, prompt_version, now, raw_response))
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


def store_score(conn, transcript_id, dimension, score, supporting_quotes, model_name, prompt_version, raw_response):
    """Persist a single dimension score. Uses INSERT OR REPLACE to handle re-scoring."""
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    cur.execute("""
        INSERT OR REPLACE INTO scores
        (transcript_id, dimension, score, supporting_quotes, scored_at, model_name, prompt_version, raw_llm_response)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (transcript_id, dimension, score, json.dumps(supporting_quotes), now, model_name, prompt_version, raw_response))
    conn.commit()


def get_scores(conn, company: str, quarter: str = None, year: int = None):
    """Fetch scores joined with transcript metadata for a company."""
    query = """
        SELECT t.company, t.quarter, t.year, t.chunk_index,
               s.dimension, s.score, s.supporting_quotes, s.scored_at
        FROM scores s
        JOIN transcripts t ON s.transcript_id = t.id
        WHERE t.company = ?
    """
    params = [company.upper()]
    if quarter:
        query += " AND t.quarter = ?"
        params.append(quarter)
    if year:
        query += " AND t.year = ?"
        params.append(year)
    query += " ORDER BY t.year, t.quarter, s.dimension"
    cur = conn.cursor()
    cur.execute(query, params)
    return cur.fetchall()
