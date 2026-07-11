"""Scaffold for trend computations over quarter-wise scoring outputs."""

import pandas as pd


def compute_qoq_score_change(scores_df: pd.DataFrame) -> pd.DataFrame:
    """
    Return quarter-over-quarter score deltas per company.

    Expected input columns include:
    company, quarter, year, and score columns like
    evasiveness, sentiment, overpromising, complexity, guidance.
    """
    raise NotImplementedError("QoQ score change computation is not implemented yet.")


def compute_rolling_3q_average(scores_df: pd.DataFrame) -> pd.DataFrame:
    """
    Return rolling 3-quarter averages for each score dimension per company.

    Expected input columns include:
    company, quarter, year, and score columns like
    evasiveness, sentiment, overpromising, complexity, guidance.
    """
    raise NotImplementedError("Rolling 3-quarter average computation is not implemented yet.")


def compute_trend_label(scores_df: pd.DataFrame) -> pd.DataFrame:
    """
    Label each metric trend as IMPROVING, STABLE, or DETERIORATING.

    Expected input columns include:
    company, quarter, year, and score columns like
    evasiveness, sentiment, overpromising, complexity, guidance.
    """
    raise NotImplementedError("Trend labeling is not implemented yet.")


def find_biggest_single_quarter_drop(scores_df: pd.DataFrame) -> pd.DataFrame:
    """
    Identify the largest single-quarter drop event per company/metric.

    Expected input columns include:
    company, quarter, year, and score columns like
    evasiveness, sentiment, overpromising, complexity, guidance.
    """
    raise NotImplementedError("Biggest single-quarter drop detection is not implemented yet.")
