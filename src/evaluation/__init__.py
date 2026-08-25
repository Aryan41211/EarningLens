"""Evaluation of LLM scores against human labels (EVALUATION.md)."""

from src.evaluation.metrics import (
    GATE_FAIL,
    GATE_PASS,
    GATE_UNMEASURED,
    TARGETS,
    directional_agreement,
    evaluate,
    evaluate_dimension,
    gate,
    gate_dimension,
    mean_absolute_error,
    meets_target,
    pair_scores_with_labels,
    spearman_correlation,
    within_n_accuracy,
)

__all__ = [
    "GATE_FAIL",
    "GATE_PASS",
    "GATE_UNMEASURED",
    "TARGETS",
    "directional_agreement",
    "evaluate",
    "evaluate_dimension",
    "gate",
    "gate_dimension",
    "mean_absolute_error",
    "meets_target",
    "pair_scores_with_labels",
    "spearman_correlation",
    "within_n_accuracy",
]
