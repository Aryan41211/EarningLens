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
            company TEXT,
            quarter TEXT,
            year INTEGER,
            dimension TEXT NOT NULL,
            score INTEGER NOT NULL,
            supporting_quotes TEXT,
            scored_at TEXT NOT NULL,
            model_name TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            raw_llm_response TEXT NOT NULL,
            FOREIGN KEY (transcript_id) REFERENCES transcripts(id)
        )
    """)
    _migrate_score_identity(conn)
    conn.commit()
    return conn


def _migrate_score_identity(conn) -> None:
    """Give scores a transcript identity that survives re-ingest.

    `transcripts` is a chunks table -- one row per chunk -- so there was never a
    transcript-level id to reference. Scores were filed under the rowid of the
    transcript's chunk 0. Because store_transcript() deletes and re-inserts
    chunks, and AUTOINCREMENT never reuses rowids, re-running Phase 1 silently
    orphaned every existing score: they vanished from the JOIN with no error.

    The fix is to denormalise (company, quarter, year) onto the score itself, so
    identity no longer depends on a rowid that ingest is free to change.
    Idempotent -- safe to call on every init_db.
    """
    cur = conn.cursor()
    existing = {row[1] for row in cur.execute("PRAGMA table_info(scores)")}

    for column, coltype in (("company", "TEXT"), ("quarter", "TEXT"), ("year", "INTEGER")):
        if column not in existing:
            cur.execute(f"ALTER TABLE scores ADD COLUMN {column} {coltype}")

    # Backfill from the chunk row the score currently points at, while that
    # link is still intact.
    cur.execute("""
        UPDATE scores
           SET company = (SELECT t.company FROM transcripts t WHERE t.id = scores.transcript_id),
               quarter = (SELECT t.quarter FROM transcripts t WHERE t.id = scores.transcript_id),
               year    = (SELECT t.year    FROM transcripts t WHERE t.id = scores.transcript_id)
         WHERE company IS NULL
           AND EXISTS (SELECT 1 FROM transcripts t WHERE t.id = scores.transcript_id)
    """)

    _migrate_score_variants(conn)
    conn.commit()


def _migrate_score_variants(conn) -> None:
    """Let one transcript hold scores from different models and prompt versions.

    Uniqueness was (company, quarter, year, dimension), so scoring a transcript
    with a revised prompt REPLACED the existing row. Comparing evasiveness-v1
    against evasiveness-v2 was therefore impossible: producing v2 destroyed the
    v1 baseline it was meant to be measured against.

    Identity is now (company, quarter, year, dimension, model_name,
    prompt_version). Variants coexist; choosing between them is a read-time
    decision, which is what check_score_comparability() already reports on.

    Removing the table-level UNIQUE(transcript_id, dimension) requires
    rebuilding the table in SQLite. Idempotent -- guarded on the constraint
    still being present.
    """
    cur = conn.cursor()
    schema = cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='scores'"
    ).fetchone()
    if not schema or "UNIQUE(transcript_id, dimension)" not in schema[0]:
        # Already migrated (or a fresh DB created with the current schema).
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_scores_variant
            ON scores(company, quarter, year, dimension, model_name, prompt_version)
        """)
        return

    cur.execute("DROP INDEX IF EXISTS idx_scores_identity")
    cur.execute("ALTER TABLE scores RENAME TO scores_old")
    cur.execute("""
        CREATE TABLE scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transcript_id INTEGER NOT NULL,
            company TEXT,
            quarter TEXT,
            year INTEGER,
            dimension TEXT NOT NULL,
            score INTEGER NOT NULL,
            supporting_quotes TEXT,
            scored_at TEXT NOT NULL,
            model_name TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            raw_llm_response TEXT NOT NULL,
            FOREIGN KEY (transcript_id) REFERENCES transcripts(id)
        )
    """)
    cur.execute("""
        INSERT INTO scores
            (transcript_id, company, quarter, year, dimension, score,
             supporting_quotes, scored_at, model_name, prompt_version, raw_llm_response)
        SELECT transcript_id, company, quarter, year, dimension, score,
               supporting_quotes, scored_at, model_name, prompt_version, raw_llm_response
        FROM scores_old
    """)
    cur.execute("DROP TABLE scores_old")
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_scores_variant
        ON scores(company, quarter, year, dimension, model_name, prompt_version)
    """)
    conn.commit()


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


def get_chunks(conn, company: str, quarter: str | None = None, year: int | None = None):
    """Fetch chunks for a company, optionally filtered by quarter/year."""
    query = "SELECT * FROM transcripts WHERE company = ?"
    params: list[object] = [company.upper()]
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
    """Persist a single dimension score. Upserts (ON CONFLICT ... DO UPDATE) on
    the full (company, quarter, year, dimension, model_name, prompt_version)
    identity, so re-scoring the same variant updates in place.

    (company, quarter, year) is resolved from transcript_id and stored on the row
    so the score keeps its identity if the transcript is later re-ingested and
    the underlying chunk rowids change.
    """
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    identity = cur.execute(
        "SELECT company, quarter, year FROM transcripts WHERE id = ?", (transcript_id,)
    ).fetchone()
    company, quarter, year = identity if identity else (None, None, None)
    # Upsert on the full variant identity: re-running the same (model, prompt)
    # updates in place, while a different model or prompt version is stored
    # alongside rather than overwriting the series it should be compared to.
    cur.execute("""
        INSERT INTO scores
        (transcript_id, company, quarter, year, dimension, score, supporting_quotes,
         scored_at, model_name, prompt_version, raw_llm_response)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(company, quarter, year, dimension, model_name, prompt_version)
        DO UPDATE SET
            transcript_id = excluded.transcript_id,
            score = excluded.score,
            supporting_quotes = excluded.supporting_quotes,
            scored_at = excluded.scored_at,
            raw_llm_response = excluded.raw_llm_response
    """, (transcript_id, company, quarter, year, dimension, score,
          json.dumps(supporting_quotes), now, model_name, prompt_version, raw_response))
    conn.commit()


def get_scores(conn, company: str, quarter: str | None = None, year: int | None = None):
    """Fetch scores for a company.

    Reads identity from the score row itself rather than joining to transcripts,
    so scores survive a re-ingest that changes chunk rowids.
    """
    query = """
        SELECT s.company, s.quarter, s.year, s.transcript_id,
               s.dimension, s.score, s.supporting_quotes, s.scored_at
        FROM scores s
        WHERE s.company = ?
    """
    params: list[object] = [company.upper()]
    if quarter:
        query += " AND s.quarter = ?"
        params.append(quarter)
    if year:
        query += " AND s.year = ?"
        params.append(year)
    query += " ORDER BY s.year, s.quarter, s.dimension"
    cur = conn.cursor()
    cur.execute(query, params)
    return cur.fetchall()
