"""
Integration test: end-to-end scoring pipeline with mocked LLM.

Tests that scoring all 5 dimensions through the shared scorer
produces correct results.
"""

import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.storage.db import init_db, store_transcript, store_score, get_scores
from src.scoring import DIMENSION_MODULES, SCORE_KEY_MAP, score_transcript_all


def _make_mock_llm_result(score_key: str, score: int, quotes: list[str]) -> dict:
    """Create a mock LLM result dict."""
    return {
        score_key: score,
        "supporting_quotes": quotes,
        "raw_response": f"raw-{score_key}",
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }


def test_scores_retrievable_after_store():
    """Store a score and verify it's retrievable via get_scores."""
    conn = init_db(":memory:")
    store_transcript(conn, "TEST", "Q1", 2025, ["chunk"], "test.pdf")
    store_score(conn, 1, "evasiveness", 8, ["q1"], "test-model", "v1", "raw")
    rows = get_scores(conn, "TEST", "Q1", 2025)
    assert len(rows) == 1
    assert rows[0][4] == "evasiveness"
    assert rows[0][5] == 8
    conn.close()


def test_scoring_pipeline_persists_all_dimensions():
    """Score all 5 dimensions on a mock transcript and verify scores are valid."""
    conn = init_db(":memory:")
    store_transcript(conn, "TEST", "Q1", 2025, ["Test chunk text."], "test.pdf")
    chunks = ["Test chunk text."]

    patches = [
        patch("src.scoring.evasiveness.score_evasiveness_llm",
              return_value=_make_mock_llm_result("evasiveness_score", 6, ["evasion quote"])),
        patch("src.scoring.evasiveness.score_evasiveness_keywords",
              return_value={"total_count": 2, "frequency": {}, "matched_phrases": [], "excerpts": []}),
        patch("src.scoring.evasiveness.find_qa_start_index", return_value=0),
        patch("src.scoring.sentiment_shift.score_dimension_llm",
              return_value=_make_mock_llm_result("sentiment_shift_score", 5, ["sq"])),
        patch("src.scoring.complexity_spike.score_dimension_llm",
              return_value=_make_mock_llm_result("complexity_spike_score", 4, ["cq"])),
        patch("src.scoring.overpromising.score_dimension_llm",
              return_value=_make_mock_llm_result("overpromising_score", 3, ["oq"])),
        patch("src.scoring.forward_guidance_vagueness.score_dimension_llm",
              return_value=_make_mock_llm_result("forward_guidance_vagueness_score", 7, ["fgq"])),
    ]

    for p in patches:
        p.start()

    try:
        for dimension in DIMENSION_MODULES:
            scorer = DIMENSION_MODULES[dimension]
            score_key = SCORE_KEY_MAP[dimension]
            result = scorer(chunks)

            llm = result.get("llm_result", result)
            score_val = llm.get(score_key)
            assert score_val is not None, f"Score missing for {dimension}"
            assert 1 <= score_val <= 10, f"Score out of range for {dimension}: {score_val}"
    finally:
        for p in patches:
            p.stop()

    conn.close()


def test_score_transcript_all_persists_every_dimension():
    """score_transcript_all must write all 5 dimensions through to the scores table."""
    conn = init_db(":memory:")
    store_transcript(conn, "TEST", "Q1", 2025, ["Test chunk text."], "test.pdf")
    tid = conn.execute("SELECT id FROM transcripts WHERE chunk_index=0").fetchone()[0]

    patches = [
        patch("src.scoring.evasiveness.score_evasiveness_llm",
              return_value=_make_mock_llm_result("evasiveness_score", 6, ["evasion quote"])),
        patch("src.scoring.evasiveness.find_qa_start_index", return_value=0),
        patch("src.scoring.sentiment_shift.score_dimension_llm",
              return_value=_make_mock_llm_result("sentiment_shift_score", 5, ["sq"])),
        patch("src.scoring.complexity_spike.score_dimension_llm",
              return_value=_make_mock_llm_result("complexity_spike_score", 4, ["cq"])),
        patch("src.scoring.overpromising.score_dimension_llm",
              return_value=_make_mock_llm_result("overpromising_score", 3, ["oq"])),
        patch("src.scoring.forward_guidance_vagueness.score_dimension_llm",
              return_value=_make_mock_llm_result("forward_guidance_vagueness_score", 7, ["fgq"])),
    ]
    for p in patches:
        p.start()
    try:
        results = score_transcript_all(conn, tid, ["Test chunk text."], model="pinned-model")
    finally:
        for p in patches:
            p.stop()

    assert set(results) == set(DIMENSION_MODULES)
    assert all(r["score"] is not None for r in results.values())

    rows = conn.execute("SELECT dimension, score, model_name FROM scores").fetchall()
    assert len(rows) == 5
    conn.close()


def test_recorded_model_name_matches_the_model_actually_used():
    """Regression test for KNOWN_ISSUES.md MEDIUM-4.

    Four of the five score_transcript_* wrappers did not accept a model
    argument, so score_transcript_all silently ignored the override while
    still recording it -- the model_name column could name a model that never
    produced the score. That is exactly the kind of drift that made the
    existing scores untrustworthy.
    """
    conn = init_db(":memory:")
    store_transcript(conn, "TEST", "Q1", 2025, ["Test chunk text."], "test.pdf")
    tid = conn.execute("SELECT id FROM transcripts WHERE chunk_index=0").fetchone()[0]

    seen_models = {}

    def _spy(dimension, score_key):
        def _inner(chunks, **kwargs):
            seen_models[dimension] = kwargs.get("model")
            return _make_mock_llm_result(score_key, 5, ["q"])
        return _inner

    patches = [
        patch("src.scoring.evasiveness.score_evasiveness_llm",
              side_effect=_spy("evasiveness", "evasiveness_score")),
        patch("src.scoring.evasiveness.find_qa_start_index", return_value=0),
        patch("src.scoring.sentiment_shift.score_dimension_llm",
              side_effect=_spy("sentiment_shift", "sentiment_shift_score")),
        patch("src.scoring.complexity_spike.score_dimension_llm",
              side_effect=_spy("complexity_spike", "complexity_spike_score")),
        patch("src.scoring.overpromising.score_dimension_llm",
              side_effect=_spy("overpromising", "overpromising_score")),
        patch("src.scoring.forward_guidance_vagueness.score_dimension_llm",
              side_effect=_spy("forward_guidance_vagueness", "forward_guidance_vagueness_score")),
    ]
    for p in patches:
        p.start()
    try:
        score_transcript_all(conn, tid, ["Test chunk text."], model="pinned-model")
    finally:
        for p in patches:
            p.stop()

    # Every dimension must have actually received the override...
    assert set(seen_models) == set(DIMENSION_MODULES), f"not all scorers called: {seen_models}"
    assert all(m == "pinned-model" for m in seen_models.values()), seen_models

    # ...and every stored row must name that same model.
    stored = {m for (m,) in conn.execute("SELECT DISTINCT model_name FROM scores")}
    assert stored == {"pinned-model"}, stored
    conn.close()
