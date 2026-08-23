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


def test_complexity_spike_score_key_in_result():
    from src.scoring.complexity_spike import score_transcript_complexity_spike
    result = score_transcript_complexity_spike(["Test chunk."])
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


def test_overpromising_score_key_in_result():
    from src.scoring.overpromising import score_transcript_overpromising
    result = score_transcript_overpromising(["Test chunk."])
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


def test_forward_guidance_vagueness_score_key_in_result():
    from src.scoring.forward_guidance_vagueness import score_transcript_forward_guidance_vagueness
    result = score_transcript_forward_guidance_vagueness(["Test chunk."])
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

        # Store twice with INSERT OR REPLACE
        store_score(conn, transcript_id, "evasiveness", 5, ["q1"], "m", "v1", "r1")
        store_score(conn, transcript_id, "evasiveness", 8, ["q2"], "m", "v2", "r2")

        rows = get_scores(conn, "TCS")
        # Should be exactly 1 row (upserted), not 2
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
