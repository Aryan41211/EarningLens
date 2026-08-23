"""
Unit tests for the 4 new scoring dimensions (sentiment_shift, complexity_spike,
overpromising, forward_guidance_vagueness).

LLM calls are mocked — no real API requests.
"""

import sys
import os
import json
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---- Shared mock helper ----

def _mock_openai_response(content):
    choice = MagicMock()
    choice.message.content = content
    mock_response = MagicMock()
    mock_response.choices = [choice]
    return mock_response


# ===========================================================
# sentiment_shift tests
# ===========================================================

def test_sentiment_shift_prompt_non_empty():
    from src.scoring.sentiment_shift import SENTIMENT_SHIFT_SYSTEM_PROMPT, _build_prompt
    assert len(SENTIMENT_SHIFT_SYSTEM_PROMPT) > 100
    prompt = _build_prompt(["Test chunk one.", "Test chunk two."])
    assert "Test chunk one." in prompt
    assert "Test chunk two." in prompt


@patch.dict("os.environ", {"LLM_API_KEY": "test-key", "LLM_API_BASE_URL": "https://test.api"})
@patch("openai.OpenAI", autospec=True)
def test_sentiment_shift_score_key_in_result(mock_openai_class):
    import importlib
    import config
    importlib.reload(config)
    import src.scoring.sentiment_shift
    importlib.reload(src.scoring.sentiment_shift)
    from src.scoring.sentiment_shift import score_transcript_sentiment_shift

    response_json = json.dumps({"sentiment_shift_score": 4, "supporting_quotes": []})
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response(response_json)
    mock_openai_class.return_value = mock_client

    result = score_transcript_sentiment_shift(["K Krithivasan: Growth was solid."])
    assert "llm_result" in result
    assert "chunks_used" in result
    assert result["chunks_used"] == 1
    # The mock must have been used — a real network call means the patch missed.
    assert mock_client.chat.completions.create.called


@patch.dict("os.environ", {"LLM_API_KEY": "test-key", "LLM_API_BASE_URL": "https://test.api"})
@patch("openai.OpenAI", autospec=True)
def test_sentiment_shift_llm_returns_score(mock_openai_class):
    import importlib
    import config
    importlib.reload(config)
    import src.scoring.sentiment_shift
    importlib.reload(src.scoring.sentiment_shift)
    from src.scoring.sentiment_shift import score_sentiment_shift_llm

    response_json = json.dumps({"sentiment_shift_score": 5, "supporting_quotes": ["Hedging detected in Q&A."]})
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response(response_json)
    mock_openai_class.return_value = mock_client

    result = score_sentiment_shift_llm(["Test chunk."])
    assert result["sentiment_shift_score"] == 5
    assert len(result["supporting_quotes"]) == 1


@patch.dict("os.environ", {"LLM_API_KEY": "test-key", "LLM_API_BASE_URL": "https://test.api"})
@patch("openai.OpenAI", autospec=True)
def test_sentiment_shift_clamps_score(mock_openai_class):
    import importlib
    import config
    importlib.reload(config)
    import src.scoring.sentiment_shift
    importlib.reload(src.scoring.sentiment_shift)
    from src.scoring.sentiment_shift import score_sentiment_shift_llm

    response_json = json.dumps({"sentiment_shift_score": 15, "supporting_quotes": ["test"]})
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response(response_json)
    mock_openai_class.return_value = mock_client

    result = score_sentiment_shift_llm(["test"])
    assert 1 <= result["sentiment_shift_score"] <= 10


@patch.dict("os.environ", {"LLM_API_KEY": "test-key", "LLM_API_BASE_URL": "https://test.api"})
@patch("openai.OpenAI", autospec=True)
def test_sentiment_shift_handles_invalid_json(mock_openai_class):
    import importlib
    import config
    importlib.reload(config)
    import src.scoring.sentiment_shift
    importlib.reload(src.scoring.sentiment_shift)
    from src.scoring.sentiment_shift import score_sentiment_shift_llm

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response("not json at all")
    mock_openai_class.return_value = mock_client

    result = score_sentiment_shift_llm(["test"])
    assert result["sentiment_shift_score"] is None
    assert "error" in result


@patch.dict("os.environ", {"LLM_API_KEY": "", "LLM_API_BASE_URL": ""})
def test_sentiment_shift_returns_empty_when_not_configured():
    import importlib
    import config
    importlib.reload(config)
    import src.scoring.sentiment_shift
    importlib.reload(src.scoring.sentiment_shift)
    from src.scoring.sentiment_shift import score_sentiment_shift_llm

    result = score_sentiment_shift_llm(["test"])
    assert result["sentiment_shift_score"] is None
    assert result["error"] == "LLM not configured"


# ===========================================================
# complexity_spike tests
# ===========================================================

def test_complexity_spike_prompt_non_empty():
    from src.scoring.complexity_spike import COMPLEXITY_SPIKE_SYSTEM_PROMPT, _build_prompt
    assert len(COMPLEXITY_SPIKE_SYSTEM_PROMPT) > 100
    prompt = _build_prompt(["Jargon-heavy paragraph."])
    assert "Jargon-heavy paragraph." in prompt


@patch.dict("os.environ", {"LLM_API_KEY": "test-key", "LLM_API_BASE_URL": "https://test.api"})
@patch("openai.OpenAI", autospec=True)
def test_complexity_spike_score_key_in_result(mock_openai_class):
    import importlib
    import config
    importlib.reload(config)
    import src.scoring.complexity_spike
    importlib.reload(src.scoring.complexity_spike)
    from src.scoring.complexity_spike import score_transcript_complexity_spike

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response(
        json.dumps({"complexity_spike_score": 4, "supporting_quotes": []})
    )
    mock_openai_class.return_value = mock_client

    result = score_transcript_complexity_spike(["Test chunk."])
    # The mock must have been used — a real network call means the patch missed.
    assert mock_client.chat.completions.create.called
    assert "llm_result" in result
    assert "chunks_used" in result


@patch.dict("os.environ", {"LLM_API_KEY": "test-key", "LLM_API_BASE_URL": "https://test.api"})
@patch("openai.OpenAI", autospec=True)
def test_complexity_spike_llm_returns_score(mock_openai_class):
    import importlib
    import config
    importlib.reload(config)
    import src.scoring.complexity_spike
    importlib.reload(src.scoring.complexity_spike)
    from src.scoring.complexity_spike import score_complexity_spike_llm

    response_json = json.dumps({"complexity_spike_score": 7, "supporting_quotes": ["Nested qualifiers everywhere."]})
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response(response_json)
    mock_openai_class.return_value = mock_client

    result = score_complexity_spike_llm(["Test chunk."])
    assert result["complexity_spike_score"] == 7
    assert len(result["supporting_quotes"]) == 1


@patch.dict("os.environ", {"LLM_API_KEY": "test-key", "LLM_API_BASE_URL": "https://test.api"})
@patch("openai.OpenAI", autospec=True)
def test_complexity_spike_clamps_score(mock_openai_class):
    import importlib
    import config
    importlib.reload(config)
    import src.scoring.complexity_spike
    importlib.reload(src.scoring.complexity_spike)
    from src.scoring.complexity_spike import score_complexity_spike_llm

    response_json = json.dumps({"complexity_spike_score": -3, "supporting_quotes": []})
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response(response_json)
    mock_openai_class.return_value = mock_client

    result = score_complexity_spike_llm(["test"])
    assert 1 <= result["complexity_spike_score"] <= 10


@patch.dict("os.environ", {"LLM_API_KEY": "", "LLM_API_BASE_URL": ""})
def test_complexity_spike_returns_empty_when_not_configured():
    import importlib
    import config
    importlib.reload(config)
    import src.scoring.complexity_spike
    importlib.reload(src.scoring.complexity_spike)
    from src.scoring.complexity_spike import score_complexity_spike_llm

    result = score_complexity_spike_llm(["test"])
    assert result["complexity_spike_score"] is None
    assert result["error"] == "LLM not configured"


# ===========================================================
# overpromising tests
# ===========================================================

def test_overpromising_prompt_non_empty():
    from src.scoring.overpromising import OVERPROMISING_SYSTEM_PROMPT, _build_prompt
    assert len(OVERPROMISING_SYSTEM_PROMPT) > 100
    prompt = _build_prompt(["Growth claims."])
    assert "Growth claims." in prompt


@patch.dict("os.environ", {"LLM_API_KEY": "test-key", "LLM_API_BASE_URL": "https://test.api"})
@patch("openai.OpenAI", autospec=True)
def test_overpromising_score_key_in_result(mock_openai_class):
    import importlib
    import config
    importlib.reload(config)
    import src.scoring.overpromising
    importlib.reload(src.scoring.overpromising)
    from src.scoring.overpromising import score_transcript_overpromising

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response(
        json.dumps({"overpromising_score": 3, "supporting_quotes": []})
    )
    mock_openai_class.return_value = mock_client

    result = score_transcript_overpromising(["Test chunk."])
    # The mock must have been used — a real network call means the patch missed.
    assert mock_client.chat.completions.create.called
    assert "llm_result" in result
    assert "chunks_used" in result


@patch.dict("os.environ", {"LLM_API_KEY": "test-key", "LLM_API_BASE_URL": "https://test.api"})
@patch("openai.OpenAI", autospec=True)
def test_overpromising_llm_returns_score(mock_openai_class):
    import importlib
    import config
    importlib.reload(config)
    import src.scoring.overpromising
    importlib.reload(src.scoring.overpromising)
    from src.scoring.overpromising import score_overpromising_llm

    response_json = json.dumps({"overpromising_score": 8, "supporting_quotes": ["Best quarter ever."]})
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response(response_json)
    mock_openai_class.return_value = mock_client

    result = score_overpromising_llm(["Test chunk."])
    assert result["overpromising_score"] == 8
    assert len(result["supporting_quotes"]) == 1


@patch.dict("os.environ", {"LLM_API_KEY": "test-key", "LLM_API_BASE_URL": "https://test.api"})
@patch("openai.OpenAI", autospec=True)
def test_overpromising_clamps_score(mock_openai_class):
    import importlib
    import config
    importlib.reload(config)
    import src.scoring.overpromising
    importlib.reload(src.scoring.overpromising)
    from src.scoring.overpromising import score_overpromising_llm

    response_json = json.dumps({"overpromising_score": 0, "supporting_quotes": []})
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response(response_json)
    mock_openai_class.return_value = mock_client

    result = score_overpromising_llm(["test"])
    assert 1 <= result["overpromising_score"] <= 10


@patch.dict("os.environ", {"LLM_API_KEY": "", "LLM_API_BASE_URL": ""})
def test_overpromising_returns_empty_when_not_configured():
    import importlib
    import config
    importlib.reload(config)
    import src.scoring.overpromising
    importlib.reload(src.scoring.overpromising)
    from src.scoring.overpromising import score_overpromising_llm

    result = score_overpromising_llm(["test"])
    assert result["overpromising_score"] is None
    assert result["error"] == "LLM not configured"


# ===========================================================
# forward_guidance_vagueness tests
# ===========================================================

def test_forward_guidance_vagueness_prompt_non_empty():
    from src.scoring.forward_guidance_vagueness import FORWARD_GUIDANCE_VAGUENESS_SYSTEM_PROMPT, _build_prompt
    assert len(FORWARD_GUIDANCE_VAGUENESS_SYSTEM_PROMPT) > 100
    prompt = _build_prompt(["Forward looking statement."])
    assert "Forward looking statement." in prompt


@patch.dict("os.environ", {"LLM_API_KEY": "test-key", "LLM_API_BASE_URL": "https://test.api"})
@patch("openai.OpenAI", autospec=True)
def test_forward_guidance_vagueness_score_key_in_result(mock_openai_class):
    import importlib
    import config
    importlib.reload(config)
    import src.scoring.forward_guidance_vagueness
    importlib.reload(src.scoring.forward_guidance_vagueness)
    from src.scoring.forward_guidance_vagueness import score_transcript_forward_guidance_vagueness

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response(
        json.dumps({"forward_guidance_vagueness_score": 6, "supporting_quotes": []})
    )
    mock_openai_class.return_value = mock_client

    result = score_transcript_forward_guidance_vagueness(["Test chunk."])
    # The mock must have been used — a real network call means the patch missed.
    assert mock_client.chat.completions.create.called
    assert "llm_result" in result
    assert "chunks_used" in result


@patch.dict("os.environ", {"LLM_API_KEY": "test-key", "LLM_API_BASE_URL": "https://test.api"})
@patch("openai.OpenAI", autospec=True)
def test_forward_guidance_vagueness_llm_returns_score(mock_openai_class):
    import importlib
    import config
    importlib.reload(config)
    import src.scoring.forward_guidance_vagueness
    importlib.reload(src.scoring.forward_guidance_vagueness)
    from src.scoring.forward_guidance_vagueness import score_forward_guidance_vagueness_llm

    response_json = json.dumps({"forward_guidance_vagueness_score": 6, "supporting_quotes": ["We remain optimistic."]})
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response(response_json)
    mock_openai_class.return_value = mock_client

    result = score_forward_guidance_vagueness_llm(["Test chunk."])
    assert result["forward_guidance_vagueness_score"] == 6
    assert len(result["supporting_quotes"]) == 1


@patch.dict("os.environ", {"LLM_API_KEY": "test-key", "LLM_API_BASE_URL": "https://test.api"})
@patch("openai.OpenAI", autospec=True)
def test_forward_guidance_vagueness_clamps_score(mock_openai_class):
    import importlib
    import config
    importlib.reload(config)
    import src.scoring.forward_guidance_vagueness
    importlib.reload(src.scoring.forward_guidance_vagueness)
    from src.scoring.forward_guidance_vagueness import score_forward_guidance_vagueness_llm

    response_json = json.dumps({"forward_guidance_vagueness_score": 12, "supporting_quotes": []})
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response(response_json)
    mock_openai_class.return_value = mock_client

    result = score_forward_guidance_vagueness_llm(["test"])
    assert 1 <= result["forward_guidance_vagueness_score"] <= 10


@patch.dict("os.environ", {"LLM_API_KEY": "", "LLM_API_BASE_URL": ""})
def test_forward_guidance_vagueness_returns_empty_when_not_configured():
    import importlib
    import config
    importlib.reload(config)
    import src.scoring.forward_guidance_vagueness
    importlib.reload(src.scoring.forward_guidance_vagueness)
    from src.scoring.forward_guidance_vagueness import score_forward_guidance_vagueness_llm

    result = score_forward_guidance_vagueness_llm(["test"])
    assert result["forward_guidance_vagueness_score"] is None
    assert result["error"] == "LLM not configured"


# ===========================================================
# scores table tests
# ===========================================================

def test_scores_table_created():
    import tempfile
    import os
    from src.storage.db import init_db
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        conn = init_db(path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scores'")
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "scores"
        conn.close()
    finally:
        os.unlink(path)


def test_store_score_and_get_scores():
    import tempfile
    import os
    from src.storage.db import init_db, store_transcript, store_score, get_scores
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        conn = init_db(path)
        # Insert a transcript first
        store_transcript(conn, "TCS", "Q1", 2025, ["chunk text here"], "TCS_Q1_2025.pdf")
        cur = conn.cursor()
        cur.execute("SELECT id FROM transcripts WHERE company='TCS' AND quarter='Q1' AND year=2025 LIMIT 1")
        transcript_id = cur.fetchone()[0]

        # Store a score
        store_score(conn, transcript_id, "evasiveness", 7, ["quote1"], "test-model", "v1", '{"raw": "response"}')

        # Retrieve it
        rows = get_scores(conn, "TCS", "Q1", 2025)
        assert len(rows) == 1
        assert rows[0][4] == "evasiveness"  # dimension
        assert rows[0][5] == 7  # score
        conn.close()
    finally:
        os.unlink(path)


def test_store_score_upsert():
    import tempfile
    import os
    from src.storage.db import init_db, store_transcript, store_score, get_scores
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        conn = init_db(path)
        store_transcript(conn, "TCS", "Q1", 2025, ["chunk text here"], "TCS_Q1_2025.pdf")
        cur = conn.cursor()
        cur.execute("SELECT id FROM transcripts WHERE company='TCS' AND quarter='Q1' AND year=2025 LIMIT 1")
        transcript_id = cur.fetchone()[0]

        # Same (model, prompt_version) twice -> updated in place, not duplicated
        store_score(conn, transcript_id, "evasiveness", 5, ["q1"], "m", "v1", "r1")
        store_score(conn, transcript_id, "evasiveness", 8, ["q2"], "m", "v1", "r2")

        rows = get_scores(conn, "TCS")
        assert len(rows) == 1
        assert rows[0][5] == 8  # latest score
        conn.close()
    finally:
        os.unlink(path)


# ===========================================================
# orchestrator import test
# ===========================================================

def test_orchestrator_imports():
    from src.scoring import DIMENSION_MODULES, SCORE_KEY_MAP
    assert "evasiveness" in DIMENSION_MODULES
    assert "sentiment_shift" in DIMENSION_MODULES
    assert "complexity_spike" in DIMENSION_MODULES
    assert "overpromising" in DIMENSION_MODULES
    assert "forward_guidance_vagueness" in DIMENSION_MODULES
    assert len(DIMENSION_MODULES) == 5
    assert len(SCORE_KEY_MAP) == 5


# ===========================================================
# Score identity survives re-ingest (KNOWN_ISSUES.md HIGH-2)
# ===========================================================

def test_scores_survive_transcript_reingest():
    """Re-running Phase 1 must not destroy existing scores.

    `transcripts` is a chunks table, so scores were filed under the rowid of
    chunk 0. store_transcript() deletes and re-inserts chunks and AUTOINCREMENT
    never reuses rowids, so a re-ingest silently orphaned every score -- they
    vanished from the JOIN with no error and no warning.

    Verified against a copy of the real database: re-ingesting a single
    transcript orphaned 5 of its 20 scores.
    """
    import sqlite3
    from src.storage.db import init_db, store_transcript, store_score, get_scores

    conn = init_db(":memory:")
    store_transcript(conn, "TCS", "Q1", 2025, ["chunk a", "chunk b"], "TCS_Q1_2025.pdf")
    tid = conn.execute("SELECT id FROM transcripts WHERE chunk_index=0").fetchone()[0]
    store_score(conn, tid, "evasiveness", 7, ["q"], "model-a", "evasiveness-v1", "{}")

    assert len(get_scores(conn, "TCS")) == 1

    # Re-ingest the same transcript: chunk rowids change
    store_transcript(conn, "TCS", "Q1", 2025, ["chunk a", "chunk b"], "TCS_Q1_2025.pdf")
    new_tid = conn.execute("SELECT id FROM transcripts WHERE chunk_index=0").fetchone()[0]
    assert new_tid != tid, "rowid should have changed; otherwise this test proves nothing"

    # The old join would now return zero rows
    orphaned = conn.execute(
        "SELECT COUNT(*) FROM scores s LEFT JOIN transcripts t ON s.transcript_id = t.id "
        "WHERE t.id IS NULL"
    ).fetchone()[0]
    assert orphaned == 1, "precondition: the rowid link is genuinely broken"

    # ...but the score is still reachable by identity
    rows = get_scores(conn, "TCS")
    assert len(rows) == 1
    assert rows[0][4] == "evasiveness"
    assert rows[0][5] == 7
    conn.close()


def test_rescoring_after_reingest_updates_the_same_variant():
    """Re-scoring with the SAME model and prompt updates in place after a re-ingest.

    The rowid changes on re-ingest, but identity is (company, quarter, year,
    dimension, model_name, prompt_version), so the row is found and updated
    rather than duplicated.
    """
    from src.storage.db import init_db, store_transcript, store_score, get_scores

    conn = init_db(":memory:")
    store_transcript(conn, "TCS", "Q1", 2025, ["chunk a"], "TCS_Q1_2025.pdf")
    tid = conn.execute("SELECT id FROM transcripts WHERE chunk_index=0").fetchone()[0]
    store_score(conn, tid, "evasiveness", 7, ["q"], "model-a", "evasiveness-v1", "{}")

    store_transcript(conn, "TCS", "Q1", 2025, ["chunk a"], "TCS_Q1_2025.pdf")
    new_tid = conn.execute("SELECT id FROM transcripts WHERE chunk_index=0").fetchone()[0]
    assert new_tid != tid
    store_score(conn, new_tid, "evasiveness", 3, ["q2"], "model-a", "evasiveness-v1", "{}")

    rows = get_scores(conn, "TCS")
    assert len(rows) == 1, f"expected one row per variant, got {len(rows)}"
    assert rows[0][5] == 3
    conn.close()


def test_different_prompt_version_is_kept_alongside_not_overwritten():
    """Scoring with a revised prompt must NOT destroy the series it is measured against.

    Uniqueness was once (company, quarter, year, dimension), so producing
    evasiveness-v2 replaced the v1 row and made the comparison impossible.
    """
    from src.storage.db import init_db, store_transcript, store_score

    conn = init_db(":memory:")
    store_transcript(conn, "TCS", "Q1", 2025, ["chunk a"], "TCS_Q1_2025.pdf")
    tid = conn.execute("SELECT id FROM transcripts WHERE chunk_index=0").fetchone()[0]

    store_score(conn, tid, "evasiveness", 7, ["q"], "model-a", "evasiveness-v1", "{}")
    store_score(conn, tid, "evasiveness", 3, ["q"], "model-a", "evasiveness-v2", "{}")

    rows = conn.execute(
        "SELECT prompt_version, score FROM scores ORDER BY prompt_version"
    ).fetchall()
    assert rows == [("evasiveness-v1", 7), ("evasiveness-v2", 3)]
    conn.close()


def test_different_model_is_kept_alongside_not_overwritten():
    """Two models on one transcript coexist, so they can be compared."""
    from src.storage.db import init_db, store_transcript, store_score

    conn = init_db(":memory:")
    store_transcript(conn, "TCS", "Q1", 2025, ["chunk a"], "TCS_Q1_2025.pdf")
    tid = conn.execute("SELECT id FROM transcripts WHERE chunk_index=0").fetchone()[0]

    store_score(conn, tid, "evasiveness", 7, ["q"], "model-a", "evasiveness-v1", "{}")
    store_score(conn, tid, "evasiveness", 4, ["q"], "model-b", "evasiveness-v1", "{}")

    rows = conn.execute("SELECT model_name, score FROM scores ORDER BY model_name").fetchall()
    assert rows == [("model-a", 7), ("model-b", 4)]
    conn.close()


def test_store_score_records_transcript_identity():
    """company/quarter/year must be resolved from transcript_id and persisted."""
    from src.storage.db import init_db, store_transcript, store_score

    conn = init_db(":memory:")
    store_transcript(conn, "INFY", "Q3", 2024, ["chunk"], "INFY_Q3_2024.pdf")
    tid = conn.execute("SELECT id FROM transcripts WHERE chunk_index=0").fetchone()[0]
    store_score(conn, tid, "overpromising", 5, [], "model-a", "overpromising-v1", "{}")

    row = conn.execute("SELECT company, quarter, year FROM scores").fetchone()
    assert row == ("INFY", "Q3", 2024)
    conn.close()


def test_scores_remain_readable_by_identity_after_reingest():
    """The real incident: `run_phase1.py --help` re-ingested (no argparse), moving
    every chunk rowid. Scores survived because identity lives on the score row,
    but any query still joining on transcript_id returned nothing.

    Guards the read path the summary output uses.
    """
    from src.storage.db import init_db, store_transcript, store_score

    conn = init_db(":memory:")
    store_transcript(conn, "TCS", "Q1", 2025, ["a", "b"], "TCS_Q1_2025.pdf")
    tid = conn.execute("SELECT id FROM transcripts WHERE chunk_index=0").fetchone()[0]
    store_score(conn, tid, "evasiveness", 7, ["q"], "m", "evasiveness-v1", "{}")

    store_transcript(conn, "TCS", "Q1", 2025, ["a", "b"], "TCS_Q1_2025.pdf")

    joined = conn.execute(
        "SELECT COUNT(*) FROM scores s JOIN transcripts t ON s.transcript_id = t.id"
    ).fetchone()[0]
    by_identity = conn.execute(
        "SELECT COUNT(*) FROM scores WHERE company IS NOT NULL"
    ).fetchone()[0]

    assert joined == 0, "precondition: the rowid join is genuinely broken"
    assert by_identity == 1, "identity read must still find the score"
    conn.close()
