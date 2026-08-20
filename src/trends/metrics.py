"""Trend computations over quarter-wise scoring outputs.

All functions accept a DataFrame with columns:
    company, quarter, year, <dimension_score_columns...>

Dimension columns are the 5 scoring dimensions from config.SCORE_DIMENSIONS:
    evasiveness, sentiment_shift, complexity_spike, overpromising, forward_guidance_vagueness

Higher scores generally indicate worse management credibility
(evasiveness=10 means very evasive, sentiment_shift=10 means large negative shift).
"""

import logging
from typing import Literal

import pandas as pd

from config import SCORE_DIMENSIONS

logger = logging.getLogger("earningslens")

# Thresholds for trend labeling (score-change magnitude to flag a trend)
_IMPROVE_THRESHOLD = -1.5   # QoQ delta <= this → IMPROVING (score went down = good)
_DETERIORATE_THRESHOLD = 1.5  # QoQ delta >= this → DETERIORATING (score went up = bad)

QuarterOrder = Literal["Q1", "Q2", "Q3", "Q4"]
_QUARTER_RANK: dict[str, int] = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}


def _quarter_sort_key(df: pd.DataFrame) -> pd.Series:
    """Return a sortable integer key from year+quarter columns."""
    return df["year"] * 10 + df["quarter"].map(_QUARTER_RANK)


def load_scores_from_db(conn) -> pd.DataFrame:
    """Load one-score-per-transcript pivot from the SQLite scores table.

    The scores table stores (transcript_id, dimension, score) rows.
    This function pivots them so each transcript is one row with columns:
        company, quarter, year, evasiveness, sentiment_shift, ...
    Only transcripts that have at least one score are included.
    """
    query = """
        SELECT t.company, t.quarter, t.year, s.dimension, s.score
        FROM scores s
        JOIN transcripts t ON s.transcript_id = t.id
        ORDER BY t.company, t.year, t.quarter, s.dimension
    """
    rows = pd.read_sql_query(query, conn)
    if rows.empty:
        logger.warning("No scores found in database.")
        return pd.DataFrame()

    pivoted = rows.pivot_table(
        index=["company", "quarter", "year"],
        columns="dimension",
        values="score",
        aggfunc="first",
    ).reset_index()
    pivoted.columns.name = None

    # Ensure all dimension columns exist (may be NaN if not yet scored)
    for dim in SCORE_DIMENSIONS:
        if dim not in pivoted.columns:
            pivoted[dim] = pd.NA

    pivoted = pivoted.sort_values(["company", "year", "quarter"], key=lambda s: _quarter_sort_key(pivoted)).reset_index(drop=True)
    return pivoted


# ---------------------------------------------------------------------------
# Core trend functions
# ---------------------------------------------------------------------------

def compute_qoq_score_change(scores_df: pd.DataFrame) -> pd.DataFrame:
    """Return quarter-over-quarter score deltas per company.

    For each company and dimension, the delta is (current_quarter - previous_quarter).
    The first quarter for each company has NaN delta (no prior data).

    Returns a DataFrame with the original columns plus <dim>_delta columns.
    """
    if scores_df.empty:
        return scores_df.copy()

    result = scores_df.copy().sort_values(["company", "year", "quarter"], key=lambda s: _quarter_sort_key(scores_df)).reset_index(drop=True)

    for dim in SCORE_DIMENSIONS:
        if dim in result.columns:
            result[f"{dim}_delta"] = result.groupby("company")[dim].diff()

    return result


def compute_rolling_3q_average(scores_df: pd.DataFrame) -> pd.DataFrame:
    """Return rolling 3-quarter averages for each score dimension per company.

    For each company and dimension, computes a rolling window of 3 quarters.
    Fewer than 3 quarters available → NaN (not enough history).

    Returns a DataFrame with the original columns plus <dim>_ma3 columns.
    """
    if scores_df.empty:
        return scores_df.copy()

    result = scores_df.copy().sort_values(["company", "year", "quarter"], key=lambda s: _quarter_sort_key(scores_df)).reset_index(drop=True)

    for dim in SCORE_DIMENSIONS:
        if dim in result.columns:
            result[f"{dim}_ma3"] = (
                result.groupby("company")[dim]
                .transform(lambda x: x.rolling(window=3, min_periods=3).mean())
            )

    return result


def compute_trend_label(scores_df: pd.DataFrame) -> pd.DataFrame:
    """Label each metric trend as IMPROVING, STABLE, or DETERIORATING.

    Uses QoQ delta thresholds:
        delta <= -1.5 → IMPROVING (score decreased = management less evasive etc.)
        delta >= +1.5 → DETERIORATING (score increased = worse credibility signal)
        otherwise     → STABLE

    Returns a DataFrame with the original columns plus <dim>_trend columns
    containing string labels.
    """
    if scores_df.empty:
        return scores_df.copy()

    df_with_delta = compute_qoq_score_change(scores_df)
    result = df_with_delta.copy()

    for dim in SCORE_DIMENSIONS:
        delta_col = f"{dim}_delta"
        trend_col = f"{dim}_trend"
        if delta_col in result.columns:
            result[trend_col] = result[delta_col].apply(
                lambda d: (
                    "IMPROVING" if pd.notna(d) and d <= _IMPROVE_THRESHOLD
                    else "DETERIORATING" if pd.notna(d) and d >= _DETERIORATE_THRESHOLD
                    else "STABLE"
                )
            )

    return result


def find_biggest_single_quarter_drop(scores_df: pd.DataFrame) -> pd.DataFrame:
    """Identify the largest single-quarter score increase (worsening) per company/metric.

    A "drop" in credibility means the score went UP (e.g., evasiveness 4 → 8).
    Returns one row per (company, dimension) with the largest positive delta,
    along with the from/to quarter and delta value.
    """
    if scores_df.empty:
        return pd.DataFrame()

    df_with_delta = compute_qoq_score_change(scores_df)
    results = []

    for dim in SCORE_DIMENSIONS:
        delta_col = f"{dim}_delta"
        if delta_col not in df_with_delta.columns:
            continue

        subset = df_with_delta.dropna(subset=[delta_col]).copy()
        if subset.empty:
            continue

        # Only consider worsening (positive score increases)
        worsening = subset[subset[delta_col] > 0]
        if worsening.empty:
            continue

        # Find the row with the largest positive delta per company
        idx = worsening.groupby("company")[delta_col].idxmax()
        worst = worsening.loc[idx, ["company", "year", "quarter", dim, delta_col]].copy()
        worst["dimension"] = dim
        worst.rename(columns={dim: "score", delta_col: "delta"}, inplace=True)

        # Compute previous quarter info
        for _, row in worst.iterrows():
            company_rows = df_with_delta[
                (df_with_delta["company"] == row["company"])
            ].sort_values(["year", "quarter"], key=lambda s: _quarter_sort_key(
                df_with_delta[df_with_delta["company"] == row["company"]]
            ))
            company_rows = company_rows.reset_index(drop=True)
            current_idx = company_rows[
                (company_rows["year"] == row["year"]) & (company_rows["quarter"] == row["quarter"])
            ].index
            if len(current_idx) > 0 and current_idx[0] > 0:
                prev = company_rows.iloc[current_idx[0] - 1]
                worst.loc[worst.index[worst["company"] == row["company"]], "prev_quarter"] = prev["quarter"]
                worst.loc[worst.index[worst["company"] == row["company"]], "prev_year"] = prev["year"]
                worst.loc[worst.index[worst["company"] == row["company"]], "prev_score"] = prev[dim]

        results.append(worst)

    if not results:
        return pd.DataFrame()

    combined = pd.concat(results, ignore_index=True)
    combined = combined.sort_values("delta", ascending=False).reset_index(drop=True)
    return combined
