"""Tests for Phase 3 trend detection metrics."""

import sys
import os
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import sqlite3

from src.storage.db import init_db, store_transcript, store_score
from src.trends.metrics import (
    check_score_comparability,
    load_scores_from_db,
    compute_qoq_score_change,
    compute_rolling_3q_average,
    compute_trend_label,
    find_biggest_single_quarter_drop,
)


@pytest.fixture
def sample_scores():
    """Three companies with 4 quarters each, all 5 dimensions scored."""
    rows = []
    companies = ["TCS", "INFY", "WIPRO"]
    quarters = ["Q1", "Q2", "Q3", "Q4"]
    # TCS: scores improve over time (go down)
    tcs_scores = [8, 7, 6, 5]
    # INFY: scores deteriorate (go up)
    infy_scores = [3, 5, 7, 9]
    # WIPRO: stable
    wipro_scores = [5, 5, 6, 5]

    for company, dim_scores in [("TCS", tcs_scores), ("INFY", infy_scores), ("WIPRO", wipro_scores)]:
        for i, q in enumerate(quarters):
            rows.append({
                "company": company,
                "quarter": q,
                "year": 2024,
                "evasiveness": dim_scores[i],
                "sentiment_shift": dim_scores[i],
                "complexity_spike": dim_scores[i],
                "overpromising": dim_scores[i],
                "forward_guidance_vagueness": dim_scores[i],
            })
    return pd.DataFrame(rows)


@pytest.fixture
def gapped_scores():
    """One company whose ingested quarters are not contiguous.

    Mirrors the real INFY data: Q1 2023, Q1 2024, Q2 2024, Q4 2025.
    Only the Q1 2024 -> Q2 2024 step is an actual quarter-over-quarter change.
    """
    return pd.DataFrame([
        {"company": "INFY", "quarter": "Q1", "year": 2023, "evasiveness": 8},
        {"company": "INFY", "quarter": "Q1", "year": 2024, "evasiveness": 2},
        {"company": "INFY", "quarter": "Q2", "year": 2024, "evasiveness": 6},
        {"company": "INFY", "quarter": "Q4", "year": 2025, "evasiveness": 6},
    ])


@pytest.fixture
def year_boundary_scores():
    """Q4 -> Q1 across a year boundary is adjacent and must not be treated as a gap."""
    return pd.DataFrame([
        {"company": "TCS", "quarter": "Q3", "year": 2023, "evasiveness": 4},
        {"company": "TCS", "quarter": "Q4", "year": 2023, "evasiveness": 5},
        {"company": "TCS", "quarter": "Q1", "year": 2024, "evasiveness": 9},
    ])


@pytest.fixture
def sparse_scores():
    """Two companies with different quarters scored — some dimensions missing."""
    return pd.DataFrame([
        {"company": "TCS", "quarter": "Q1", "year": 2024, "evasiveness": 7, "sentiment_shift": 5},
        {"company": "TCS", "quarter": "Q2", "year": 2024, "evasiveness": 8, "sentiment_shift": 6},
        {"company": "INFY", "quarter": "Q1", "year": 2024, "evasiveness": 4},
    ])


class TestComputeQoQScoreChange:
    def test_returns_delta_columns(self, sample_scores):
        result = compute_qoq_score_change(sample_scores)
        for dim in ["evasiveness", "sentiment_shift", "complexity_spike", "overpromising", "forward_guidance_vagueness"]:
            assert f"{dim}_delta" in result.columns

    def test_first_quarter_has_nan_delta(self, sample_scores):
        result = compute_qoq_score_change(sample_scores)
        tcs_q1 = result[(result["company"] == "TCS") & (result["quarter"] == "Q1")]
        assert tcs_q1["evasiveness_delta"].isna().all()

    def test_tcs_improvement_shows_negative_delta(self, sample_scores):
        result = compute_qoq_score_change(sample_scores)
        tcs_q2 = result[(result["company"] == "TCS") & (result["quarter"] == "Q2")]
        assert tcs_q2["evasiveness_delta"].iloc[0] == -1

    def test_infy_deterioration_shows_positive_delta(self, sample_scores):
        result = compute_qoq_score_change(sample_scores)
        infy_q2 = result[(result["company"] == "INFY") & (result["quarter"] == "Q2")]
        assert infy_q2["evasiveness_delta"].iloc[0] == 2

    def test_empty_input(self):
        result = compute_qoq_score_change(pd.DataFrame())
        assert result.empty

    def test_sparse_scores_preserves_gaps(self, sparse_scores):
        result = compute_qoq_score_change(sparse_scores)
        infy = result[result["company"] == "INFY"]
        assert infy["evasiveness_delta"].isna().all()  # only 1 quarter


class TestComputeRolling3qAverage:
    def test_returns_ma3_columns(self, sample_scores):
        result = compute_rolling_3q_average(sample_scores)
        for dim in ["evasiveness", "sentiment_shift", "complexity_spike", "overpromising", "forward_guidance_vagueness"]:
            assert f"{dim}_ma3" in result.columns

    def test_first_two_quarters_are_nan(self, sample_scores):
        result = compute_rolling_3q_average(sample_scores)
        tcs = result[result["company"] == "TCS"].sort_values("quarter")
        assert tcs.iloc[0]["evasiveness_ma3"] != tcs.iloc[0]["evasiveness_ma3"]  # NaN check
        assert tcs.iloc[1]["evasiveness_ma3"] != tcs.iloc[1]["evasiveness_ma3"]

    def test_third_quarter_has_value(self, sample_scores):
        result = compute_rolling_3q_average(sample_scores)
        tcs_q3 = result[(result["company"] == "TCS") & (result["quarter"] == "Q3")]
        expected = (8 + 7 + 6) / 3
        assert abs(tcs_q3["evasiveness_ma3"].iloc[0] - expected) < 0.01

    def test_fourth_quarter_rolling(self, sample_scores):
        result = compute_rolling_3q_average(sample_scores)
        tcs_q4 = result[(result["company"] == "TCS") & (result["quarter"] == "Q4")]
        expected = (7 + 6 + 5) / 3
        assert abs(tcs_q4["evasiveness_ma3"].iloc[0] - expected) < 0.01

    def test_empty_input(self):
        result = compute_rolling_3q_average(pd.DataFrame())
        assert result.empty


class TestComputeTrendLabel:
    def test_returns_trend_columns(self, sample_scores):
        result = compute_trend_label(sample_scores)
        for dim in ["evasiveness", "sentiment_shift", "complexity_spike", "overpromising", "forward_guidance_vagueness"]:
            assert f"{dim}_trend" in result.columns

    def test_improving_detected(self, sample_scores):
        result = compute_trend_label(sample_scores)
        tcs_q2 = result[(result["company"] == "TCS") & (result["quarter"] == "Q2")]
        assert tcs_q2["evasiveness_trend"].iloc[0] == "STABLE"  # delta=-1, within threshold

    def test_deteriorating_detected(self, sample_scores):
        result = compute_trend_label(sample_scores)
        infy_q2 = result[(result["company"] == "INFY") & (result["quarter"] == "Q2")]
        assert infy_q2["evasiveness_trend"].iloc[0] == "DETERIORATING"  # delta=+2

    def test_stable_for_small_changes(self, sample_scores):
        result = compute_trend_label(sample_scores)
        wipro_q2 = result[(result["company"] == "WIPRO") & (result["quarter"] == "Q2")]
        assert wipro_q2["evasiveness_trend"].iloc[0] == "STABLE"  # delta=0

    def test_first_quarter_is_stable(self, sample_scores):
        result = compute_trend_label(sample_scores)
        tcs_q1 = result[(result["company"] == "TCS") & (result["quarter"] == "Q1")]
        assert tcs_q1["evasiveness_trend"].iloc[0] == "STABLE"  # NaN delta → STABLE

    def test_empty_input(self):
        result = compute_trend_label(pd.DataFrame())
        assert result.empty


class TestFindBiggestSingleQuarterDrop:
    def test_returns_dimension_column(self, sample_scores):
        result = find_biggest_single_quarter_drop(sample_scores)
        assert "dimension" in result.columns

    def test_infy_has_worst_drop(self, sample_scores):
        result = find_biggest_single_quarter_drop(sample_scores)
        # Only INFY has worsening scores (positive deltas)
        assert "INFY" in result["company"].values

    def test_delta_is_positive_for_worsening(self, sample_scores):
        result = find_biggest_single_quarter_drop(sample_scores)
        assert (result["delta"] > 0).all()

    def test_sorted_by_delta_descending(self, sample_scores):
        result = find_biggest_single_quarter_drop(sample_scores)
        if not result.empty:
            assert result["delta"].is_monotonic_decreasing

    def test_empty_input(self):
        result = find_biggest_single_quarter_drop(pd.DataFrame())
        assert result.empty


class TestCalendarGaps:
    """Regression tests for KNOWN_ISSUES.md HIGH-3.

    diff() differences adjacent rows, not adjacent quarters. Without a period
    check, a jump across missing quarters is reported as a quarter-over-quarter
    change and is indistinguishable from a real one.
    """

    def test_delta_is_nan_across_a_gap(self, gapped_scores):
        result = compute_qoq_score_change(gapped_scores)
        row = result[(result["year"] == 2024) & (result["quarter"] == "Q1")].iloc[0]
        # Q1 2023 -> Q1 2024 is four quarters apart, not one
        assert pd.isna(row["evasiveness_delta"])

    def test_delta_is_computed_for_adjacent_quarters(self, gapped_scores):
        result = compute_qoq_score_change(gapped_scores)
        row = result[(result["year"] == 2024) & (result["quarter"] == "Q2")].iloc[0]
        assert row["evasiveness_delta"] == 4.0

    def test_delta_is_nan_across_a_multi_year_gap(self, gapped_scores):
        result = compute_qoq_score_change(gapped_scores)
        row = result[(result["year"] == 2025) & (result["quarter"] == "Q4")].iloc[0]
        assert pd.isna(row["evasiveness_delta"])

    def test_year_boundary_counts_as_adjacent(self, year_boundary_scores):
        result = compute_qoq_score_change(year_boundary_scores)
        row = result[(result["year"] == 2024) & (result["quarter"] == "Q1")].iloc[0]
        # Q4 2023 -> Q1 2024 is one quarter apart
        assert row["evasiveness_delta"] == 4.0

    def test_rolling_average_is_nan_when_window_spans_a_gap(self, gapped_scores):
        result = compute_rolling_3q_average(gapped_scores)
        # Q1 2023 / Q1 2024 / Q2 2024 is three rows but not three consecutive quarters
        row = result[(result["year"] == 2024) & (result["quarter"] == "Q2")].iloc[0]
        assert pd.isna(row["evasiveness_ma3"])

    def test_rolling_average_computed_over_contiguous_window(self, year_boundary_scores):
        result = compute_rolling_3q_average(year_boundary_scores)
        row = result[(result["year"] == 2024) & (result["quarter"] == "Q1")].iloc[0]
        assert row["evasiveness_ma3"] == pytest.approx(6.0)

    def test_trend_label_is_stable_across_a_gap(self, gapped_scores):
        result = compute_trend_label(gapped_scores)
        row = result[(result["year"] == 2024) & (result["quarter"] == "Q1")].iloc[0]
        # A NaN delta must not be labelled IMPROVING just because 8 -> 2
        assert row["evasiveness_trend"] == "STABLE"

    def test_biggest_drop_ignores_gapped_jumps(self, gapped_scores):
        result = find_biggest_single_quarter_drop(gapped_scores)
        assert len(result) == 1
        assert result.iloc[0]["delta"] == 4.0
        assert result.iloc[0]["prev_quarter"] == "Q1"
        assert result.iloc[0]["prev_year"] == 2024


class TestOrdering:
    """Regression test for KNOWN_ISSUES.md MEDIUM-1."""

    def test_rows_are_grouped_by_company_not_interleaved(self, sample_scores):
        result = compute_qoq_score_change(sample_scores)
        companies = result["company"].tolist()
        # Each company's rows must be contiguous
        assert companies == sorted(companies, key=companies.index)
        for company in set(companies):
            positions = [i for i, c in enumerate(companies) if c == company]
            assert positions == list(range(positions[0], positions[-1] + 1))

    def test_internal_period_column_is_not_leaked(self, sample_scores):
        for fn in (compute_qoq_score_change, compute_rolling_3q_average, compute_trend_label):
            assert "_period" not in fn(sample_scores).columns


# ---------------------------------------------------------------------------
# Score comparability (KNOWN_ISSUES.md BLOCKER-2)
# ---------------------------------------------------------------------------

def _db_with_scores(tmp_path, rows):
    """Build a throwaway DB. rows = [(quarter, year, dimension, score, model)]."""
    conn = init_db(str(tmp_path / "t.db"))
    seen = set()
    for quarter, year, dimension, score, model in rows:
        if (quarter, year) not in seen:
            store_transcript(conn, "TCS", quarter, year, ["chunk text"], "TCS.pdf")
            seen.add((quarter, year))
        tid = conn.execute(
            "SELECT id FROM transcripts WHERE quarter=? AND year=? AND chunk_index=0",
            (quarter, year),
        ).fetchone()[0]
        store_score(conn, tid, dimension, score, [], model, f"{dimension}-v1", "{}")
    return conn


class TestScoreComparability:
    """A delta only means something if every score in the series was produced
    the same way. The live DB had evasiveness scores from three models, which
    made the dashboard's top alert a model artifact."""

    def test_single_model_is_clean(self, tmp_path):
        conn = _db_with_scores(tmp_path, [
            ("Q1", 2024, "evasiveness", 4, "model-a"),
            ("Q2", 2024, "evasiveness", 6, "model-a"),
        ])
        assert check_score_comparability(conn).empty

    def test_mixed_models_are_reported(self, tmp_path):
        conn = _db_with_scores(tmp_path, [
            ("Q1", 2024, "evasiveness", 4, "model-a"),
            ("Q2", 2024, "evasiveness", 6, "model-b"),
        ])
        report = check_score_comparability(conn)
        assert len(report) == 1
        assert report.iloc[0]["dimension"] == "evasiveness"
        assert report.iloc[0]["variants"] == 2
        assert "model-a" in report.iloc[0]["detail"]
        assert "model-b" in report.iloc[0]["detail"]

    def test_only_the_contaminated_dimension_is_reported(self, tmp_path):
        conn = _db_with_scores(tmp_path, [
            ("Q1", 2024, "evasiveness", 4, "model-a"),
            ("Q2", 2024, "evasiveness", 6, "model-b"),
            ("Q1", 2024, "overpromising", 3, "model-a"),
            ("Q2", 2024, "overpromising", 3, "model-a"),
        ])
        report = check_score_comparability(conn)
        assert report["dimension"].tolist() == ["evasiveness"]

    def test_empty_db_is_clean(self, tmp_path):
        conn = init_db(str(tmp_path / "empty.db"))
        assert check_score_comparability(conn).empty

    def test_strict_load_raises_on_mixed_models(self, tmp_path):
        conn = _db_with_scores(tmp_path, [
            ("Q1", 2024, "evasiveness", 4, "model-a"),
            ("Q2", 2024, "evasiveness", 6, "model-b"),
        ])
        with pytest.raises(ValueError, match="mixed-model"):
            load_scores_from_db(conn, strict=True)

    def test_non_strict_load_still_returns_data(self, tmp_path):
        conn = _db_with_scores(tmp_path, [
            ("Q1", 2024, "evasiveness", 4, "model-a"),
            ("Q2", 2024, "evasiveness", 6, "model-b"),
        ])
        assert len(load_scores_from_db(conn)) == 2

    def test_strict_load_passes_when_clean(self, tmp_path):
        conn = _db_with_scores(tmp_path, [
            ("Q1", 2024, "evasiveness", 4, "model-a"),
            ("Q2", 2024, "evasiveness", 6, "model-a"),
        ])
        assert len(load_scores_from_db(conn, strict=True)) == 2
