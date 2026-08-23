"""Tests for recovering scores from truncated LLM responses.

A response cut off by the token limit used to be discarded whole, which
silently shrank the batch divisor. Because truncation happens when the model
emits long supporting quotes, the dropout was not independent of what was
being scored -- so the aggregate was biased, not merely noisy.

ALL LLM CALLS ARE MOCKED.
"""

import json
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.scoring._llm_dimension_scorer import (  # noqa: E402
    _salvage_truncated_json,
    _finish_reason,
)

# A real shape: the score lands before the quote list, then the response is cut
# off partway through the second quote.
TRUNCATED = (
    '{"evasiveness_score": 7, "supporting_quotes": '
    '["Nilanjan Roy: \\"The top-end has come down.\\"", '
    '"Salil Parekh: \\"So here, the way we have built this guidance is bas'
)


def _mock_openai_response(content, finish_reason="stop"):
    choice = MagicMock()
    choice.message.content = content
    choice.finish_reason = finish_reason
    response = MagicMock()
    response.choices = [choice]
    return response


# ---------------------------------------------------------------
# _salvage_truncated_json
# ---------------------------------------------------------------

def test_salvage_recovers_score_from_truncated_response():
    result = _salvage_truncated_json(TRUNCATED, "evasiveness_score")
    assert result is not None
    assert result["evasiveness_score"] == 7


def test_salvage_keeps_only_quotes_that_closed():
    result = _salvage_truncated_json(TRUNCATED, "evasiveness_score")
    # The second quote was cut mid-string and must not be returned.
    assert len(result["supporting_quotes"]) == 1


def test_salvage_unescapes_quotes_inside_a_quote():
    result = _salvage_truncated_json(TRUNCATED, "evasiveness_score")
    assert result["supporting_quotes"][0] == 'Nilanjan Roy: "The top-end has come down."'


def test_salvage_returns_none_when_no_score_present():
    cut = '{"supporting_quotes": ["a quote that never rea'
    assert _salvage_truncated_json(cut, "evasiveness_score") is None


def test_salvage_returns_none_on_unrelated_text():
    assert _salvage_truncated_json("not json at all", "evasiveness_score") is None


def test_salvage_ignores_a_different_dimensions_score_key():
    raw = '{"overpromising_score": 9, "supporting_quotes": ['
    assert _salvage_truncated_json(raw, "evasiveness_score") is None


def test_salvage_handles_a_response_with_no_quote_list_at_all():
    raw = '{"evasiveness_score": 4'
    result = _salvage_truncated_json(raw, "evasiveness_score")
    assert result["evasiveness_score"] == 4
    assert result["supporting_quotes"] == []


def test_finish_reason_reads_the_first_choice():
    assert _finish_reason(_mock_openai_response("x", finish_reason="length")) == "length"


def test_finish_reason_is_none_without_choices():
    empty = MagicMock()
    empty.choices = []
    assert _finish_reason(empty) is None


# ---------------------------------------------------------------
# End to end through the scorer
# ---------------------------------------------------------------

def _reload_evasiveness():
    import importlib
    import config
    importlib.reload(config)
    import src.scoring.evasiveness
    importlib.reload(src.scoring.evasiveness)
    from src.scoring.evasiveness import score_evasiveness_llm
    return score_evasiveness_llm


@patch.dict("os.environ", {"LLM_API_KEY": "test-key", "LLM_API_BASE_URL": "https://test.api"})
@patch("openai.OpenAI", autospec=True)
def test_truncated_response_still_produces_a_score(mock_openai_class):
    score_evasiveness_llm = _reload_evasiveness()

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response(
        TRUNCATED, finish_reason="length"
    )
    mock_openai_class.return_value = mock_client

    result = score_evasiveness_llm(["K Krithivasan: We remain committed to growth."])
    assert result["evasiveness_score"] == 7
    assert result["batches_used"] == result["batches_total"]


@patch.dict("os.environ", {"LLM_API_KEY": "test-key", "LLM_API_BASE_URL": "https://test.api"})
@patch("openai.OpenAI", autospec=True)
def test_unsalvageable_batch_is_reported_not_hidden(mock_openai_class):
    score_evasiveness_llm = _reload_evasiveness()

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response("not json at all")
    mock_openai_class.return_value = mock_client

    result = score_evasiveness_llm(["test chunk"])
    assert result["evasiveness_score"] is None
    assert "error" in result


@patch.dict("os.environ", {"LLM_API_KEY": "test-key", "LLM_API_BASE_URL": "https://test.api"})
@patch("openai.OpenAI", autospec=True)
def test_valid_json_is_still_parsed_strictly(mock_openai_class):
    score_evasiveness_llm = _reload_evasiveness()

    good = json.dumps({"evasiveness_score": 5, "supporting_quotes": ["a", "b", "c"]})
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response(good)
    mock_openai_class.return_value = mock_client

    result = score_evasiveness_llm(["test chunk"])
    assert result["evasiveness_score"] == 5
    assert len(result["supporting_quotes"]) == 3
