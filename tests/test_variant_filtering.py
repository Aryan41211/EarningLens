"""Regression tests for selecting one comparable (model, prompt_version) slice.

The scores table accumulates several variants per transcript. Until these
fixes, every reader of that table -- the trends CLI, the dashboard, the
evaluation harness -- either mixed the variants together or crashed when asked
to narrow to one. See KNOWN_ISSUES.md BLOCKER-2.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.storage.db import init_db, store_transcript, store_score
from src.trends.metrics import (
    check_score_comparability,
    compute_rolling_3q_average,
    compute_trend_label,
    load_scores_from_db,
)


def _chunk0_id(conn, quarter, year):
    """Scores are filed under the rowid of the transcript's first chunk."""
    return conn.execute(
        "SELECT id FROM transcripts WHERE quarter=? AND year=? AND chunk_index=0",
        (quarter, year),
    ).fetchone()[0]


@pytest.fixture
def mixed_db(tmp_path):
    """One transcript series scored twice: an old model and the pinned one.

    Mirrors the real database, where evasiveness spans several models.
    """
    conn = init_db(str(tmp_path / "t.db"))
    quarters = [("Q1", 2024), ("Q2", 2024), ("Q3", 2024)]
    for i, (q, y) in enumerate(quarters):
        store_transcript(conn, "TCS", q, y, [f"chunk text {i}"], "TCS.pdf")
        tid = _chunk0_id(conn, q, y)
        # Old model: flat 5s. Pinned model: a rising series.
        store_score(conn, tid, "evasiveness", 5, [], "old-model",
                    "evasiveness-v1", "{}")
        store_score(conn, tid, "evasiveness", 3 + i * 3, [], "pinned-model",
                    "evasiveness-v2", "{}")
    yield conn
    conn.close()


class TestComparabilityFiltering:
    def test_unfiltered_reports_contamination(self, mixed_db):
        report = check_score_comparability(mixed_db)
        assert not report.empty
        assert "evasiveness" in set(report["dimension"])

    def test_filtering_to_one_variant_is_clean(self, mixed_db):
        report = check_score_comparability(
            mixed_db, model="pinned-model", prompt_version="evasiveness-v2"
        )
        assert report.empty, "a single (model, prompt_version) slice is a valid series"

    def test_prompt_version_alone_can_still_be_mixed(self, mixed_db):
        """A prompt version is not a variant -- it can span several models.

        This is what made run_evaluation.py crash: it cleared the guard on
        --prompt-version alone, then hit duplicate rows in the merge.
        """
        store_transcript(mixed_db, "TCS", "Q4", 2024, ["chunk text 3"], "TCS.pdf")
        store_score(mixed_db, _chunk0_id(mixed_db, "Q4", 2024), "evasiveness", 7,
                    [], "another-model", "evasiveness-v2", "{}")
        report = check_score_comparability(mixed_db, prompt_version="evasiveness-v2")
        assert not report.empty

    def test_load_respects_the_filter(self, mixed_db):
        df = load_scores_from_db(
            mixed_db, model="pinned-model", prompt_version="evasiveness-v2"
        )
        assert sorted(df["evasiveness"].tolist()) == [3, 6, 9]

    def test_strict_passes_on_a_clean_slice(self, mixed_db):
        """strict=True must not raise once the caller has narrowed to one variant."""
        df = load_scores_from_db(
            mixed_db, strict=True,
            model="pinned-model", prompt_version="evasiveness-v2",
        )
        assert len(df) == 3

    def test_strict_still_raises_when_unfiltered(self, mixed_db):
        with pytest.raises(ValueError, match="mixed-model"):
            load_scores_from_db(mixed_db, strict=True)


class TestUnscoredDimensions:
    def test_unscored_dimension_is_float_not_object(self, mixed_db):
        """pd.NA columns are object dtype and .rolling() raises TypeError on them."""
        df = load_scores_from_db(
            mixed_db, model="pinned-model", prompt_version="evasiveness-v2"
        )
        assert df["overpromising"].dtype.kind == "f"

    def test_rolling_average_survives_an_unscored_dimension(self, mixed_db):
        """Regression: this raised TypeError once a filter emptied four columns."""
        df = load_scores_from_db(
            mixed_db, model="pinned-model", prompt_version="evasiveness-v2"
        )
        result = compute_rolling_3q_average(df)
        assert result["overpromising_ma3"].isna().all()
        # The scored dimension still computes: mean(3, 6, 9) == 6.
        assert result["evasiveness_ma3"].iloc[2] == pytest.approx(6.0)

    def test_unscored_dimension_is_labelled_no_data(self, mixed_db):
        """An unmeasured dimension must not read as STABLE."""
        df = load_scores_from_db(
            mixed_db, model="pinned-model", prompt_version="evasiveness-v2"
        )
        labels = compute_trend_label(df)
        assert set(labels["overpromising_trend"]) == {"NO DATA"}

    def test_scored_dimension_keeps_its_labels(self, mixed_db):
        df = load_scores_from_db(
            mixed_db, model="pinned-model", prompt_version="evasiveness-v2"
        )
        labels = compute_trend_label(df)
        # 3 -> 6 is +3, well past the +1.5 deterioration threshold.
        assert labels["evasiveness_trend"].iloc[1] == "DETERIORATING"
        assert "NO DATA" not in set(labels["evasiveness_trend"])
