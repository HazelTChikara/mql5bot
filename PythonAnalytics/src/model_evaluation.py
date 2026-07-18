"""Small, dependency-light scorecard for future binary quality models."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BinaryModelScorecard:
    observations: int
    accuracy: float
    precision: float
    recall: float
    brier_score: float


def evaluate_binary_probabilities(
    actual: np.ndarray, probabilities: np.ndarray, *, threshold: float = 0.5
) -> BinaryModelScorecard:
    actual = np.asarray(actual, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    if actual.shape != probabilities.shape or actual.ndim != 1:
        raise ValueError("actual and probabilities must be one-dimensional with equal length")
    if len(actual) == 0 or not np.isin(actual, [0, 1]).all():
        raise ValueError("actual must contain binary observations")
    if not np.isfinite(probabilities).all() or ((probabilities < 0) | (probabilities > 1)).any():
        raise ValueError("probabilities must be finite values in [0, 1]")
    predicted = probabilities >= threshold
    true_positive = int(((actual == 1) & predicted).sum())
    false_positive = int(((actual == 0) & predicted).sum())
    false_negative = int(((actual == 1) & ~predicted).sum())
    return BinaryModelScorecard(
        observations=len(actual),
        accuracy=float(np.mean(predicted == actual)),
        precision=true_positive / (true_positive + false_positive)
        if true_positive + false_positive
        else 0.0,
        recall=true_positive / (true_positive + false_negative)
        if true_positive + false_negative
        else 0.0,
        brier_score=float(np.mean((probabilities - actual) ** 2)),
    )
