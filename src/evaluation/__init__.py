"""Evaluation of LLM scores against human labels (EVALUATION.md)."""

from src.evaluation.metrics import (
    TARGETS,
    directional_agreement,
    evaluate,
    evaluate_dimension,
    mean_absolute_error,
    meets_target,
    pair_scores_with_labels,
    spearman_correlation,
    within_n_accuracy,
)

__all__ = [
    "TARGETS",
    "directional_agreement",
    "evaluate",
    "evaluate_dimension",
    "mean_absolute_error",
    "meets_target",
    "pair_scores_with_labels",
    "spearman_correlation",
    "within_n_accuracy",
]
