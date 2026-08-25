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

# Thresholds for trend labelling (score-change magnitude to flag a trend).
#
# These are only meaningful if they sit above the model's own run-to-run noise:
# if scoring the same transcript twice can differ by 2 points, a "DETERIORATING"
# label is the model talking to itself. Measured on 2026-08-23 with
# scripts/run_self_consistency.py -- openai/gpt-oss-120b, temperature 0.1,
# TCS Q1 2025 evasiveness, 5 runs: scores [8,8,8,8,8], spread 0.
#
# So +/-1.5 clears the noise floor comfortably for this model. Re-measure and
# revisit these if the pinned model changes; cross-model variance on that same
# transcript was 2 points, which would swamp them (EVALUATION.md section 3.3).
_IMPROVE_THRESHOLD = -1.5   # QoQ delta <= this → IMPROVING (score went down = good)
_DETERIORATE_THRESHOLD = 1.5  # QoQ delta >= this → DETERIORATING (score went up = bad)

QuarterOrder = Literal["Q1", "Q2", "Q3", "Q4"]
_QUARTER_RANK: dict[str, int] = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}


_PERIOD_COL = "_period"


def _period_index(df: pd.DataFrame) -> pd.Series:
    """Absolute quarter index, so consecutive quarters differ by exactly 1.

    2023 Q4 -> 8095, 2024 Q1 -> 8096. This is what makes calendar gaps
    detectable: a delta is only quarter-over-quarter if the index difference
    is 1.
    """
    return df["year"] * 4 + df["quarter"].map(_QUARTER_RANK) - 1


def _sorted_by_period(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy sorted by company, then chronologically within each company.

    Adds the internal _period column; callers must strip it before returning
    to the caller (see _drop_period).

    Do not be tempted to collapse this back into
    ``sort_values([...], key=lambda s: ...)``: sort_values applies key to each
    'by' column independently, so a key that ignores its argument silently
    rewrites the company column too, sorting everything by period alone.
    """
    result = df.copy()
    result[_PERIOD_COL] = _period_index(result)
    return result.sort_values(["company", _PERIOD_COL]).reset_index(drop=True)


def _drop_period(df: pd.DataFrame) -> pd.DataFrame:
    """Remove the internal period column from a result frame."""
    return df.drop(columns=[_PERIOD_COL], errors="ignore")


def check_score_comparability(
    conn,
    model: str | None = None,
    prompt_version: str | None = None,
) -> pd.DataFrame:
    """Report dimensions whose scores span more than one model or prompt version.

    A quarter-over-quarter delta only means something if every score in the
    series was produced the same way. `scores` records `model_name` and
    `prompt_version` per row but nothing enforces that they are constant, so a
    model switch mid-project shows up as a management trend.

    Args:
        conn: SQLite connection.
        model / prompt_version: restrict the check to that slice. Callers that
            display a filtered series must pass the same filter here, or the
            banner describes rows the reader is not being shown -- and, worse,
            a slice that is genuinely clean still gets flagged as contaminated.

    Returns one row per offending dimension with the variants found, or an
    empty DataFrame when every dimension is clean.
    """
    rows = pd.read_sql_query(
        """
        SELECT dimension, model_name, prompt_version, COUNT(*) AS n
        FROM scores
        WHERE (? IS NULL OR model_name = ?)
          AND (? IS NULL OR prompt_version = ?)
        GROUP BY dimension, model_name, prompt_version
        ORDER BY dimension, n DESC
        """,
        conn,
        params=[model, model, prompt_version, prompt_version],
    )
    if rows.empty:
        return pd.DataFrame()

    counts = rows.groupby("dimension").size()
    contaminated = counts[counts > 1].index
    if len(contaminated) == 0:
        return pd.DataFrame()

    report = (
        rows[rows["dimension"].isin(contaminated)]
        .groupby("dimension")
        .apply(
            lambda g: pd.Series({
                "variants": len(g),
                "detail": ", ".join(
                    f"{m}/{p} ({n})"
                    for m, p, n in zip(g["model_name"], g["prompt_version"], g["n"])
                ),
            }),
            include_groups=False,
        )
        .reset_index()
    )
    return report


def load_scores_from_db(
    conn,
    strict: bool = False,
    model: str | None = None,
    prompt_version: str | None = None,
) -> pd.DataFrame:
    """Load one-score-per-transcript pivot from the SQLite scores table.

    The scores table stores (transcript_id, dimension, score) rows.
    This function pivots them so each transcript is one row with columns:
        company, quarter, year, evasiveness, sentiment_shift, ...
    Only transcripts that have at least one score are included.

    Args:
        conn: SQLite connection.
        strict: raise ValueError if any dimension spans more than one
            (model_name, prompt_version). Default False so existing data stays
            readable, but the contamination is always logged at ERROR.
        model / prompt_version: restrict to one variant. Since a transcript can
            now hold scores from several models and prompt versions, this is how
            a caller asks for a specific series. With neither given, the most
            recently scored variant wins per (company, quarter, year, dimension).
    """
    report = check_score_comparability(conn, model=model, prompt_version=prompt_version)
    if not report.empty:
        for _, row in report.iterrows():
            logger.error(
                "Dimension %s is not a valid series: %d model/prompt variants - %s. "
                "Deltas across these scores measure the model change, not the company.",
                row["dimension"], row["variants"], row["detail"],
            )
        if strict:
            raise ValueError(
                "Refusing to build trends from mixed-model scores: "
                + "; ".join(f"{r['dimension']} ({r['variants']} variants)" for _, r in report.iterrows())
                + ". Re-score these dimensions with a single pinned model."
            )

    # Read identity from the score row, not from a join to the chunks table:
    # chunk rowids change on re-ingest, the company/quarter/year do not.
    #
    # A transcript may hold several variants (model x prompt version). Without an
    # explicit filter, take the most recent per group rather than silently
    # averaging incomparable numbers together.
    query = """
        SELECT company, quarter, year, dimension, score
        FROM scores s
        WHERE company IS NOT NULL
          AND (? IS NULL OR model_name = ?)
          AND (? IS NULL OR prompt_version = ?)
          AND scored_at = (
              SELECT MAX(scored_at) FROM scores x
              WHERE x.company = s.company AND x.quarter = s.quarter
                AND x.year = s.year AND x.dimension = s.dimension
                AND (? IS NULL OR x.model_name = ?)
                AND (? IS NULL OR x.prompt_version = ?)
          )
        ORDER BY company, year, quarter, dimension
    """
    params = [model, model, prompt_version, prompt_version,
              model, model, prompt_version, prompt_version]
    rows = pd.read_sql_query(query, conn, params=params)
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

    # Ensure all dimension columns exist (may be NaN if not yet scored).
    #
    # These must be float64, not object. A column filled with pd.NA is object
    # dtype, and .rolling() raises TypeError on it -- so an unscored dimension
    # crashed compute_rolling_3q_average rather than yielding NaN. It only
    # stayed hidden while every dimension happened to have at least one score;
    # filtering to one (model, prompt_version) makes the empty columns real.
    for dim in SCORE_DIMENSIONS:
        if dim not in pivoted.columns:
            pivoted[dim] = float("nan")
        pivoted[dim] = pd.to_numeric(pivoted[dim], errors="coerce")

    return _drop_period(_sorted_by_period(pivoted))


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

    result = _sorted_by_period(scores_df)

    # Only a one-quarter step is a quarter-over-quarter change. Where a company
    # has a calendar gap, diff() would silently report the jump across it.
    period_gap = result.groupby("company")[_PERIOD_COL].diff()
    is_adjacent = period_gap == 1

    for dim in SCORE_DIMENSIONS:
        if dim in result.columns:
            result[f"{dim}_delta"] = result.groupby("company")[dim].diff().where(is_adjacent)

    return _drop_period(result)


def compute_rolling_3q_average(scores_df: pd.DataFrame) -> pd.DataFrame:
    """Return rolling 3-quarter averages for each score dimension per company.

    For each company and dimension, computes a rolling window of 3 quarters.
    Fewer than 3 quarters available → NaN (not enough history).

    Returns a DataFrame with the original columns plus <dim>_ma3 columns.
    """
    if scores_df.empty:
        return scores_df.copy()

    result = _sorted_by_period(scores_df)

    # A 3-quarter window is only meaningful over 3 *consecutive* quarters.
    # span == 2 means rows i-2..i cover exactly three adjacent periods.
    span = result.groupby("company")[_PERIOD_COL].diff(2)
    is_contiguous_window = span == 2

    for dim in SCORE_DIMENSIONS:
        if dim in result.columns:
            result[f"{dim}_ma3"] = (
                result.groupby("company")[dim]
                .transform(lambda x: x.rolling(window=3, min_periods=3).mean())
                .where(is_contiguous_window)
            )

    return _drop_period(result)


def compute_trend_label(scores_df: pd.DataFrame) -> pd.DataFrame:
    """Label each metric trend as IMPROVING, STABLE, or DETERIORATING.

    Uses QoQ delta thresholds:
        delta <= -1.5 → IMPROVING (score decreased = management less evasive etc.)
        delta >= +1.5 → DETERIORATING (score increased = worse credibility signal)
        otherwise     → STABLE

    A dimension with no score for that transcript is labelled NO DATA, not
    STABLE. "Stable" is a claim about the company; an unscored dimension
    supports no claim at all, and rendering it as STABLE put a reassuring
    label on a measurement that was never taken -- visible wherever four of
    five dimensions are unscored, which is the current state of the database.

    A scored row whose delta is NaN (first quarter, or a calendar gap) stays
    STABLE, which is the tested behaviour.

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
            if dim in result.columns:
                result.loc[result[dim].isna(), trend_col] = "NO DATA"

    return result


def find_biggest_single_quarter_drop(scores_df: pd.DataFrame) -> pd.DataFrame:
    """Identify the largest single-quarter score increase (worsening) per company/metric.

    A "drop" in credibility means the score went UP (e.g., evasiveness 4 → 8).
    Returns one row per (company, dimension) with the largest positive delta,
    along with the from/to quarter and delta value.
    """
    if scores_df.empty:
        return pd.DataFrame()

    # Deltas are gap-aware, so a non-null delta always has an immediately
    # preceding quarter — the previous row within the company is that quarter.
    df_with_delta = _sorted_by_period(compute_qoq_score_change(scores_df))
    grouped = df_with_delta.groupby("company")
    df_with_delta["prev_quarter"] = grouped["quarter"].shift(1)
    df_with_delta["prev_year"] = grouped["year"].shift(1)

    results = []

    for dim in SCORE_DIMENSIONS:
        delta_col = f"{dim}_delta"
        if delta_col not in df_with_delta.columns:
            continue

        # Only consider worsening (positive score increases)
        worsening = df_with_delta[df_with_delta[delta_col] > 0].copy()
        if worsening.empty:
            continue

        worsening["prev_score"] = grouped[dim].shift(1)[worsening.index]

        # Find the row with the largest positive delta per company
        idx = worsening.groupby("company")[delta_col].idxmax()
        worst = worsening.loc[
            idx,
            ["company", "year", "quarter", dim, delta_col,
             "prev_quarter", "prev_year", "prev_score"],
        ].copy()
        worst["dimension"] = dim
        worst.rename(columns={dim: "score", delta_col: "delta"}, inplace=True)

        results.append(worst)

    if not results:
        return pd.DataFrame()

    combined = pd.concat(results, ignore_index=True)
    combined = combined.sort_values("delta", ascending=False).reset_index(drop=True)
    return combined
