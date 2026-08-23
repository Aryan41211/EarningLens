"""Tests for evaluation metrics (EVALUATION.md section 3.2)."""

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.evaluation import (
    directional_agreement,
    evaluate,
    mean_absolute_error,
    meets_target,
    pair_scores_with_labels,
    spearman_correlation,
    within_n_accuracy,
)


def _paired(rows):
    """rows = [(company, quarter, year, llm, human)]"""
    return pd.DataFrame(
        [
            {"company": c, "quarter": q, "year": y, "dimension": "evasiveness",
             "llm_score": llm, "human_score": human}
            for c, q, y, llm, human in rows
        ]
    )


class TestMeanAbsoluteError:
    def test_perfect_agreement_is_zero(self):
        assert mean_absolute_error(_paired([("TCS", "Q1", 2024, 5, 5)])) == 0.0

    def test_averages_absolute_gaps(self):
        # gaps of 2 and 4 -> 3.0; sign must not cancel
        df = _paired([("TCS", "Q1", 2024, 7, 5), ("TCS", "Q2", 2024, 1, 5)])
        assert mean_absolute_error(df) == 3.0

    def test_empty_is_none(self):
        assert mean_absolute_error(_paired([])) is None


class TestSpearman:
    def test_perfect_ranking_is_one(self):
        df = _paired([("TCS", "Q1", 2024, 2, 1), ("TCS", "Q2", 2024, 5, 4),
                      ("TCS", "Q3", 2024, 9, 8)])
        assert spearman_correlation(df) == pytest.approx(1.0)

    def test_inverted_ranking_is_negative_one(self):
        df = _paired([("TCS", "Q1", 2024, 9, 1), ("TCS", "Q2", 2024, 5, 4),
                      ("TCS", "Q3", 2024, 2, 8)])
        assert spearman_correlation(df) == pytest.approx(-1.0)

    def test_offset_but_ordered_still_correlates_perfectly(self):
        """A model that is consistently 3 points high still ranks correctly.

        This is why MAE alone is the wrong headline metric.
        """
        df = _paired([("TCS", "Q1", 2024, 4, 1), ("TCS", "Q2", 2024, 7, 4),
                      ("TCS", "Q3", 2024, 9, 6)])
        assert spearman_correlation(df) == pytest.approx(1.0)
        assert mean_absolute_error(df) == 3.0

    def test_constant_scores_return_none_not_zero(self):
        """No variance means no ranking; 0.0 would look like a measured result."""
        df = _paired([("TCS", "Q1", 2024, 5, 3), ("TCS", "Q2", 2024, 5, 7)])
        assert spearman_correlation(df) is None

    def test_single_pair_is_none(self):
        assert spearman_correlation(_paired([("TCS", "Q1", 2024, 5, 5)])) is None


class TestWithinN:
    def test_counts_fraction_within_tolerance(self):
        df = _paired([("TCS", "Q1", 2024, 5, 5), ("TCS", "Q2", 2024, 7, 5),
                      ("TCS", "Q3", 2024, 9, 5), ("TCS", "Q4", 2024, 1, 5)])
        # gaps 0, 2, 4, 4 -> two within 2
        assert within_n_accuracy(df, 2) == 0.5

    def test_boundary_is_inclusive(self):
        assert within_n_accuracy(_paired([("TCS", "Q1", 2024, 7, 5)]), 2) == 1.0


class TestDirectionalAgreement:
    def test_agreeing_moves(self):
        df = _paired([("TCS", "Q1", 2024, 4, 3), ("TCS", "Q2", 2024, 7, 6)])
        value, n = directional_agreement(df)
        assert value == 1.0 and n == 1

    def test_opposing_moves(self):
        df = _paired([("TCS", "Q1", 2024, 4, 6), ("TCS", "Q2", 2024, 7, 3)])
        value, n = directional_agreement(df)
        assert value == 0.0 and n == 1

    def test_skips_non_adjacent_quarters(self):
        """A jump across missing quarters is not a quarter-over-quarter move.

        Same rule as src/trends/metrics.py — otherwise the metric measures
        something the product never claims.
        """
        df = _paired([("INFY", "Q1", 2023, 8, 7), ("INFY", "Q1", 2024, 2, 6)])
        value, n = directional_agreement(df)
        assert value is None and n == 0

    def test_year_boundary_is_adjacent(self):
        df = _paired([("TCS", "Q4", 2023, 4, 3), ("TCS", "Q1", 2024, 7, 6)])
        value, n = directional_agreement(df)
        assert value == 1.0 and n == 1

    def test_does_not_compare_across_companies(self):
        df = _paired([("TCS", "Q1", 2024, 4, 3), ("INFY", "Q2", 2024, 9, 1)])
        value, n = directional_agreement(df)
        assert n == 0

    def test_both_flat_counts_as_agreement(self):
        df = _paired([("TCS", "Q1", 2024, 5, 5), ("TCS", "Q2", 2024, 5, 5)])
        value, n = directional_agreement(df)
        assert value == 1.0 and n == 1


class TestPairing:
    def _scores(self):
        return pd.DataFrame([
            {"company": "TCS", "quarter": "Q1", "year": 2024,
             "dimension": "evasiveness", "score": 7},
            {"company": "TCS", "quarter": "Q2", "year": 2024,
             "dimension": "evasiveness", "score": 4},
        ])

    def test_joins_on_identity(self):
        labels = pd.DataFrame([
            {"company": "TCS", "quarter": "Q1", "year": 2024,
             "dimension": "evasiveness", "human_score": 5},
        ])
        paired = pair_scores_with_labels(self._scores(), labels)
        assert len(paired) == 1
        assert paired.iloc[0]["llm_score"] == 7
        assert paired.iloc[0]["human_score"] == 5

    def test_blank_human_scores_are_dropped(self):
        """An unfilled template row must not become a silent zero."""
        labels = pd.DataFrame([
            {"company": "TCS", "quarter": "Q1", "year": 2024,
             "dimension": "evasiveness", "human_score": None},
        ])
        assert pair_scores_with_labels(self._scores(), labels).empty

    def test_label_without_a_score_is_excluded(self):
        labels = pd.DataFrame([
            {"company": "WIPRO", "quarter": "Q1", "year": 2024,
             "dimension": "evasiveness", "human_score": 5},
        ])
        assert pair_scores_with_labels(self._scores(), labels).empty

    def test_missing_column_raises(self):
        with pytest.raises(ValueError, match="human_score"):
            pair_scores_with_labels(self._scores(), pd.DataFrame([
                {"company": "TCS", "quarter": "Q1", "year": 2024, "dimension": "evasiveness"}
            ]))


class TestTargets:
    def test_mae_is_lower_is_better(self):
        assert meets_target("mae", 1.0) is True
        assert meets_target("mae", 2.0) is False

    def test_others_are_higher_is_better(self):
        assert meets_target("spearman", 0.9) is True
        assert meets_target("spearman", 0.1) is False

    def test_unmeasured_is_none(self):
        assert meets_target("spearman", None) is None


class TestEvaluate:
    def test_reports_per_dimension(self):
        df = _paired([("TCS", "Q1", 2024, 7, 5), ("TCS", "Q2", 2024, 4, 4)])
        results = evaluate(df)
        assert set(results) == {"evasiveness"}
        assert results["evasiveness"]["n"] == 2
        assert results["evasiveness"]["mae"] == 1.0
