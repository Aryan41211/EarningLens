"""Metrics comparing LLM scores against human labels.

The four metrics here answer different questions, and they can disagree:

- MAE asks "how far off is a typical score?"
- Spearman asks "does it rank transcripts in the right order?"
- Within-N asks "how often is it close enough to act on?"
- Directional agreement asks "when it says a company got worse, did it?"

The last one matters most. EarningsLens claims *this quarter is worse than
last quarter*, not *this quarter is a 7* — so a model that is consistently two
points high but always moves in the right direction is useful, and one with
perfect average error that moves randomly is not.

No scipy: Spearman is computed as the Pearson correlation of average ranks, a
pure-pandas/numpy operation. This matches scipy.stats.spearmanr (which itself
does rankdata(method='average') then Pearson on the ranks) without adding a
dependency (PROJECT_RULES.md keeps the stack small), and it is covered by a
test pinning the exact tie behaviour.
"""

import logging

import numpy as np
import pandas as pd

from config import SCORE_DIMENSIONS

logger = logging.getLogger("earningslens")

_QUARTER_RANK: dict[str, int] = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}

# Targets from EVALUATION.md section 3.2. A dimension meeting all four is
# "usable"; these are judgement calls, not derived constants.
TARGETS = {
    "mae": 1.5,               # lower is better
    "spearman": 0.6,          # higher is better
    "within_2": 0.7,          # higher is better
    "directional_agreement": 0.7,
}


def _period_index(df: pd.DataFrame) -> pd.Series:
    """Absolute quarter index; consecutive quarters differ by exactly 1."""
    return df["year"] * 4 + df["quarter"].map(_QUARTER_RANK) - 1


def mean_absolute_error(paired: pd.DataFrame) -> float | None:
    """Average absolute gap between llm_score and human_score."""
    if paired.empty:
        return None
    return float((paired["llm_score"] - paired["human_score"]).abs().mean())


def _spearman_rho(x: pd.Series, y: pd.Series) -> float:
    """Pearson correlation of average ranks -- Spearman with tie handling.

    scipy's spearmanr ranks with method='average' and returns the Pearson
    correlation of the ranks; this replicates it exactly without importing
    scipy. pandas' own .corr(method='spearman') is NOT usable: it delegates to
    scipy and raises ModuleNotFoundError in a clean environment where scipy is
    not installed -- which is precisely why this module implements it.
    """
    x_rank = pd.Series(x).rank(method="average")
    y_rank = pd.Series(y).rank(method="average")
    return float(np.corrcoef(x_rank, y_rank)[0, 1])


def spearman_correlation(paired: pd.DataFrame) -> float | None:
    """Rank correlation. None when undefined (fewer than 2 pairs, or no variance).

    A constant column has no ranks to correlate — pandas returns NaN rather
    than raising, and reporting that as 0.0 would look like a measured result
    instead of an absent one.
    """
    if len(paired) < 2:
        return None
    if paired["llm_score"].nunique() < 2 or paired["human_score"].nunique() < 2:
        return None
    value = _spearman_rho(paired["llm_score"], paired["human_score"])
    return None if pd.isna(value) else float(value)


def within_n_accuracy(paired: pd.DataFrame, n: int = 2) -> float | None:
    """Fraction of scores within n points of the human label."""
    if paired.empty:
        return None
    return float(((paired["llm_score"] - paired["human_score"]).abs() <= n).mean())


def directional_agreement(paired: pd.DataFrame) -> tuple[float | None, int]:
    """Fraction of quarter-over-quarter moves where LLM and human agree on direction.

    Only *adjacent* quarters count — comparing across a gap would measure
    something the product never claims (the same reasoning as
    src/trends/metrics.py). Quarters where both are flat count as agreement;
    pairs where exactly one is flat count as disagreement.

    Returns (agreement_fraction, n_comparisons). The count matters: 1.0 from
    two comparisons is not evidence.
    """
    if len(paired) < 2:
        return None, 0

    df = paired.copy()
    df["_period"] = _period_index(df)
    df = df.sort_values(["company", "_period"]).reset_index(drop=True)

    grouped = df.groupby("company")
    df["_gap"] = grouped["_period"].diff()
    df["_llm_delta"] = grouped["llm_score"].diff()
    df["_human_delta"] = grouped["human_score"].diff()

    adjacent = df[df["_gap"] == 1].dropna(subset=["_llm_delta", "_human_delta"])
    if adjacent.empty:
        return None, 0

    agree = np.sign(adjacent["_llm_delta"]) == np.sign(adjacent["_human_delta"])
    return float(agree.mean()), int(len(adjacent))


def pair_scores_with_labels(scores: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    """Inner-join stored scores to human labels on (company, quarter, year, dimension).

    Rows without a counterpart on either side are dropped and logged — a label
    for an unscored transcript, or a score nobody reviewed, cannot contribute to
    an error metric.
    """
    required_scores = {"company", "quarter", "year", "dimension", "score"}
    required_labels = {"company", "quarter", "year", "dimension", "human_score"}
    missing = required_scores - set(scores.columns)
    if missing:
        raise ValueError(f"scores missing column(s): {', '.join(sorted(missing))}")
    missing = required_labels - set(labels.columns)
    if missing:
        raise ValueError(f"labels missing column(s): {', '.join(sorted(missing))}")

    labels = labels.dropna(subset=["human_score"]).copy()
    labels["human_score"] = labels["human_score"].astype(float)

    keys = ["company", "quarter", "year", "dimension"]
    paired = scores.merge(
        labels[keys + ["human_score"]], on=keys, how="inner", validate="one_to_one"
    ).rename(columns={"score": "llm_score"})

    unmatched_labels = len(labels) - len(paired)
    if unmatched_labels > 0:
        logger.warning(
            "%d human label(s) had no matching score and were excluded.", unmatched_labels
        )
    return paired


def evaluate_dimension(paired: pd.DataFrame) -> dict:
    """Compute all four metrics for one dimension's paired scores."""
    direction, n_comparisons = directional_agreement(paired)
    return {
        "n": len(paired),
        "mae": mean_absolute_error(paired),
        "spearman": spearman_correlation(paired),
        "within_2": within_n_accuracy(paired, 2),
        "directional_agreement": direction,
        "n_direction_comparisons": n_comparisons,
    }


def evaluate(paired: pd.DataFrame) -> dict[str, dict]:
    """Compute metrics per dimension present in the paired frame."""
    return {
        dimension: evaluate_dimension(paired[paired["dimension"] == dimension])
        for dimension in SCORE_DIMENSIONS
        if not paired[paired["dimension"] == dimension].empty
    }


def meets_target(metric: str, value: float | None) -> bool | None:
    """Whether a metric value clears its target. None when unmeasured."""
    if value is None or metric not in TARGETS:
        return None
    if metric == "mae":
        return value <= TARGETS["mae"]
    return value >= TARGETS[metric]


# ---- Release gate ----
#
# The four metrics above were reported and then discarded: run_evaluation.py
# printed "FAIL" four times and exited 0, so no script, no CI job and no
# release step could act on the result. A target nothing enforces is a target
# nobody keeps -- the same reasoning that put a checksum behind prompt versions
# in src/scoring/prompts.py.

GATE_PASS = "PASS"
GATE_FAIL = "FAIL"
GATE_UNMEASURED = "UNMEASURED"


def gate_dimension(metrics: dict) -> tuple[str, list[str]]:
    """Release verdict for one dimension. Returns (status, offending metrics).

    UNMEASURED is deliberately not PASS. A metric that could not be computed --
    a score column with no variance, or no adjacent quarters to difference --
    is an absent result, not a satisfied one, and treating absence as success
    is precisely how an unvalidated claim reaches a user.
    """
    failed = [m for m in TARGETS if meets_target(m, metrics.get(m)) is False]
    if failed:
        return GATE_FAIL, failed
    unmeasured = [m for m in TARGETS if meets_target(m, metrics.get(m)) is None]
    if unmeasured:
        return GATE_UNMEASURED, unmeasured
    return GATE_PASS, []


def gate(results: dict[str, dict]) -> tuple[str, dict[str, tuple[str, list[str]]]]:
    """Release verdict across every evaluated dimension.

    Any FAIL fails the whole gate; otherwise any UNMEASURED leaves it
    UNMEASURED. An empty result set is UNMEASURED, never PASS.
    """
    per_dimension = {d: gate_dimension(m) for d, m in results.items()}
    statuses = {status for status, _ in per_dimension.values()}
    if GATE_FAIL in statuses:
        return GATE_FAIL, per_dimension
    if GATE_UNMEASURED in statuses or not per_dimension:
        return GATE_UNMEASURED, per_dimension
    return GATE_PASS, per_dimension
