"""
Unit tests for evasiveness scoring.

Keyword matching is tested directly.
LLM calls are mocked — no real API requests.
"""

import sys
import os
import json
from unittest.mock import patch, MagicMock, PropertyMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.scoring.evasiveness import (
    DODGE_PHRASES,
    score_evasiveness_keywords,
    find_qa_start_index,
    score_evasiveness_llm,
    score_transcript_evasiveness,
)


# ---------------------------------------------------------------
# Keyword matching tests
# ---------------------------------------------------------------

def test_dodge_phrase_list_not_empty():
    assert len(DODGE_PHRASES) > 10
    for p in DODGE_PHRASES:
        assert isinstance(p, str)
        assert len(p.strip()) > 3


def test_keyword_matching_finds_single_phrase():
    chunks = ["We remain committed to our growth strategy going forward."]
    result = score_evasiveness_keywords(chunks)
    assert result["total_count"] >= 1
    matched_phrases = [m["phrase"] for m in result["matched_phrases"]]
    assert "going forward" in matched_phrases


def test_keyword_matching_is_case_insensitive():
    chunks = ["Going Forward, As I Mentioned earlier, WE REMAIN COMMITTED to this."]
    result = score_evasiveness_keywords(chunks)
    matched_phrases = [m["phrase"] for m in result["matched_phrases"]]
    assert "going forward" in matched_phrases
    assert "as I mentioned" in matched_phrases
    assert "we remain committed" in matched_phrases


def test_keyword_matching_empty_chunks():
    result = score_evasiveness_keywords([])
    assert result["total_count"] == 0
    assert result["matched_phrases"] == []


def test_keyword_matching_no_dodge_phrases():
    chunks = ["Revenue grew 5% year-over-year. Operating margin was 24.1%."]
    result = score_evasiveness_keywords(chunks)
    assert result["total_count"] == 0


def test_keyword_matching_counts_frequency():
    chunks = [
        "Going forward we plan to expand. Going forward margins will improve.",
        "We remain committed to the strategy. We remain committed to growth.",
    ]
    result = score_evasiveness_keywords(chunks)
    freq = result["frequency"]
    assert freq["going forward"] == 2
    assert freq["we remain committed"] == 2


def test_keyword_matching_returns_context():
    chunks = ["The company remains optimistic about future growth this quarter."]
    result = score_evasiveness_keywords(chunks)
    # "we remain optimistic" should NOT match "remains optimistic" (different subject)
    # But "remain" might trigger if "remain optimistic" overlaps
    for m in result["matched_phrases"]:
        assert "context" in m


def test_keyword_matching_multiple_chunks():
    chunks = [
        "We continue to believe in the strategy.",
        "Too early to say what Q2 holds.",
        "Cannot speculate on merger timing.",
    ]
    result = score_evasiveness_keywords(chunks)
    assert result["total_count"] >= 2


# ---------------------------------------------------------------
# Q&A detection tests
# ---------------------------------------------------------------

def test_find_qa_start_found():
    chunks = [
        "K Krithivasan: Growth was solid.",
        "Moderator: We will now begin. We'll take our first question from the line of Ankur.",
        "Ankur Rudra: How do you see margins?",
        "K Krithivasan: We remain committed.",
    ]
    idx = find_qa_start_index(chunks)
    assert idx == 1


def test_find_qa_start_not_found():
    chunks = [
        "K Krithivasan: Growth was solid.",
        "Milind Lakkad: Attrition is 12%.",
    ]
    idx = find_qa_start_index(chunks)
    assert idx == -1


def test_find_qa_start_empty():
    assert find_qa_start_index([]) == -1


# ---------------------------------------------------------------
# LLM scoring tests (ALL MOCKED)
# ---------------------------------------------------------------

MOCK_LLM_RESPONSE = json.dumps({
    "evasiveness_score": 7,
    "supporting_quotes": [
        "We remain committed to our strategy going forward.",
        "Too early to say at this point.",
        "We continue to believe in the long-term outlook."
    ]
})


def _mock_openai_response(content=MOCK_LLM_RESPONSE):
    choice = MagicMock()
    choice.message.content = content
    mock_response = MagicMock()
    mock_response.choices = [choice]
    return mock_response


@patch.dict("os.environ", {"LLM_API_KEY": "test-key", "LLM_API_BASE_URL": "https://test.api"})
@patch("openai.OpenAI", autospec=True)
def test_llm_scoring_returns_score(mock_openai_class):
    # Reload config and evasiveness modules to pick up patched env vars
    import importlib
    import config
    importlib.reload(config)
    import src.scoring.evasiveness
    importlib.reload(src.scoring.evasiveness)
    from src.scoring.evasiveness import score_evasiveness_llm

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response()
    mock_openai_class.return_value = mock_client

    result = score_evasiveness_llm(["K Krithivasan: We remain committed to growth."])
    assert result["evasiveness_score"] == 7
    assert len(result["supporting_quotes"]) == 3


@patch.dict("os.environ", {"LLM_API_KEY": "test-key", "LLM_API_BASE_URL": "https://test.api"})
@patch("openai.OpenAI", autospec=True)
def test_llm_scoring_clamps_score(mock_openai_class):
    import importlib
    import config
    importlib.reload(config)
    import src.scoring.evasiveness
    importlib.reload(src.scoring.evasiveness)
    from src.scoring.evasiveness import score_evasiveness_llm

    mock_client = MagicMock()
    ext_response = json.dumps({"evasiveness_score": 15, "supporting_quotes": ["test"]})
    mock_client.chat.completions.create.return_value = _mock_openai_response(ext_response)
    mock_openai_class.return_value = mock_client

    result = score_evasiveness_llm(["test chunk"])
    assert 1 <= result["evasiveness_score"] <= 10


@patch.dict("os.environ", {"LLM_API_KEY": "test-key", "LLM_API_BASE_URL": "https://test.api"})
@patch("openai.OpenAI", autospec=True)
def test_llm_scoring_handles_invalid_json(mock_openai_class):
    import importlib
    import config
    importlib.reload(config)
    import src.scoring.evasiveness
    importlib.reload(src.scoring.evasiveness)
    from src.scoring.evasiveness import score_evasiveness_llm

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response("not json at all")
    mock_openai_class.return_value = mock_client

    result = score_evasiveness_llm(["test"])
    assert result["evasiveness_score"] is None
    assert "error" in result
    assert result["raw_response"] == "not json at all"


@patch.dict("os.environ", {"LLM_API_KEY": "", "LLM_API_BASE_URL": ""})
def test_llm_scoring_returns_empty_when_not_configured():
    import importlib
    import config
    importlib.reload(config)
    import src.scoring.evasiveness
    importlib.reload(src.scoring.evasiveness)
    from src.scoring.evasiveness import score_evasiveness_llm

    result = score_evasiveness_llm(["test"])
    assert result["evasiveness_score"] is None
    assert result["error"] == "LLM not configured"


@patch("src.scoring.evasiveness.score_evasiveness_llm")
def test_combined_scoring_no_qa(mock_llm):
    mock_llm.return_value = {"evasiveness_score": 5, "supporting_quotes": ["test"]}
    chunks = ["K Krithivasan: Growth was solid.", "Milind Lakkad: Attrition is 12%."]
    result = score_transcript_evasiveness(chunks)
    assert result["qa_detected"] is False
    assert "keyword_result" in result
    mock_llm.assert_not_called()


@patch.dict("os.environ", {"LLM_API_KEY": "test-key", "LLM_API_BASE_URL": "https://test.api"})
@patch("openai.OpenAI", autospec=True)
def test_combined_scoring_with_qa(mock_openai_class):
    import importlib
    import config
    importlib.reload(config)
    import src.scoring.evasiveness
    importlib.reload(src.scoring.evasiveness)
    from src.scoring.evasiveness import score_transcript_evasiveness

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response()
    mock_openai_class.return_value = mock_client

    chunks = [
        "K Krithivasan: Growth was solid.",
        "Moderator: We'll take our first question from the line of Ankur.",
        "Ankur Rudra: How do you see margins?",
        "K Krithivasan: We remain committed to growth.",
    ]
    result = score_transcript_evasiveness(chunks)
    assert result["qa_detected"] is True
    assert result["qa_chunks_used"] >= 1
    assert result["llm_result"]["evasiveness_score"] is not None