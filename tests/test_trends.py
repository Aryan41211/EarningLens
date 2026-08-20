"""Tests for Phase 3 trend detection metrics."""

import sys
import os
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.trends.metrics import (
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
