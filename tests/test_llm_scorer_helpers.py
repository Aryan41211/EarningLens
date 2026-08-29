"""Tests for the pure helpers in _llm_dimension_scorer: batching and retry-after.

_batch_chunks decides what reaches the LLM, so empty input must never become a
spurious API call (which the model would answer by guessing). _parse_retry_after
must cope with both phrasings Groq actually emits ("try again in ..." and
"retry in ...") or the backoff silently falls back to a fixed wait.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.scoring._llm_dimension_scorer import (  # noqa: E402
    _batch_chunks,
    _parse_retry_after,
)


# ---------------------------------------------------------------
# _batch_chunks
# ---------------------------------------------------------------

def test_batch_chunks_empty_input_returns_no_batches():
    assert _batch_chunks([]) == []


def test_batch_chunks_single_chunk_stays_in_one_batch():
    assert _batch_chunks(["one two three"]) == [["one two three"]]


def test_batch_chunks_splits_on_word_target():
    chunks = ["a b c d e", "f g h i j", "k l m n o"]
    batches = _batch_chunks(chunks, target_words=5)
    # ["a b c"] -> 5 words, then the next chunks each land in their own batch
    assert len(batches) == 3
    assert sum(len(b) for b in batches) == 3


# ---------------------------------------------------------------
# _parse_retry_after
# ---------------------------------------------------------------

def test_parse_retry_after_handles_try_again_phrasing():
    assert _parse_retry_after("Please try again in 4.5s.") == 4.5


def test_parse_retry_after_handles_retry_phrasing():
    assert _parse_retry_after("Rate limit exceeded. Please retry in 7m39s.") == 459.0


def test_parse_retry_after_matches_minute_second_format():
    assert _parse_retry_after("try again in 23m46.032s") == 1426.032


def test_parse_retry_after_none_when_no_wait_given():
    assert _parse_retry_after("Rate limit exceeded.") is None
