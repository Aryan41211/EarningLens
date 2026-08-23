"""Tests that a resumed sweep skips on (model, prompt_version), not model alone.

`--skip-scored` is how a sweep that exceeds the daily token budget is finished
in slices. If it matched on model alone it would treat a transcript scored at
evasiveness-v1 as already done during a v2 sweep, step over exactly the
transcripts that still need scoring, and leave permanent holes in the v2
series -- silently, because a skip is not an error.
"""

import importlib.util
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.storage.db import init_db, store_transcript, store_score  # noqa: E402

_RUNNER = os.path.join(os.path.dirname(__file__), "..", "scripts", "run_all_scoring.py")


def _load_runner():
    """Import run_all_scoring.py by path -- scripts/ is not a package on sys.path."""
    spec = importlib.util.spec_from_file_location("run_all_scoring", os.path.abspath(_RUNNER))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODEL = "openai/gpt-oss-120b"


def _seed(conn, company, quarter, year, chunks=("some transcript text",)):
    store_transcript(conn, company, quarter, year, list(chunks), f"{company}_{quarter}_{year}.pdf")
    row = conn.execute(
        "SELECT id FROM transcripts WHERE company=? AND quarter=? AND year=? AND chunk_index=0",
        (company, quarter, year),
    ).fetchone()
    return row[0]


def _score(conn, transcript_id, version, model=MODEL, dimension="evasiveness"):
    store_score(conn, transcript_id, dimension, 6, ["a quote"], model, version, "raw")


def test_v1_score_does_not_mark_a_transcript_done_for_v2():
    runner = _load_runner()
    conn = init_db(":memory:")
    tid = _seed(conn, "INFY", "Q1", 2024)
    _score(conn, tid, "evasiveness-v1")

    scored = runner.get_scored_on_model(
        conn, ["evasiveness"], MODEL, {"evasiveness": "evasiveness-v2"}
    )
    assert ("INFY", "Q1", 2024) not in scored
    conn.close()


def test_v2_score_does_mark_a_transcript_done_for_v2():
    runner = _load_runner()
    conn = init_db(":memory:")
    tid = _seed(conn, "INFY", "Q1", 2023)
    _score(conn, tid, "evasiveness-v2")

    scored = runner.get_scored_on_model(
        conn, ["evasiveness"], MODEL, {"evasiveness": "evasiveness-v2"}
    )
    assert ("INFY", "Q1", 2023) in scored
    conn.close()


def test_a_different_model_at_the_same_version_is_not_done():
    runner = _load_runner()
    conn = init_db(":memory:")
    tid = _seed(conn, "TCS", "Q2", 2024)
    _score(conn, tid, "evasiveness-v2", model="openai/gpt-oss-20b")

    scored = runner.get_scored_on_model(
        conn, ["evasiveness"], MODEL, {"evasiveness": "evasiveness-v2"}
    )
    assert ("TCS", "Q2", 2024) not in scored
    conn.close()


def test_defaults_to_the_registered_version_when_none_requested():
    runner = _load_runner()
    conn = init_db(":memory:")
    tid = _seed(conn, "TCS", "Q3", 2024)
    _score(conn, tid, "evasiveness-v1")

    # No explicit version: the run would write the registered default (v1),
    # so a v1 row does mean this transcript is done.
    scored = runner.get_scored_on_model(conn, ["evasiveness"], MODEL, {})
    assert ("TCS", "Q3", 2024) in scored
    conn.close()


def test_a_transcript_missing_one_requested_dimension_is_not_done():
    runner = _load_runner()
    conn = init_db(":memory:")
    tid = _seed(conn, "TCS", "Q4", 2025)
    _score(conn, tid, "evasiveness-v2", dimension="evasiveness")

    scored = runner.get_scored_on_model(
        conn,
        ["evasiveness", "overpromising"],
        MODEL,
        {"evasiveness": "evasiveness-v2"},
    )
    assert ("TCS", "Q4", 2025) not in scored
    conn.close()
