"""Interfaces for later model research; no production model is enabled in v1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import pandas as pd


@dataclass(frozen=True)
class TrainingMetadata:
    model_version: str
    trained_at_utc: str
    feature_names: tuple[str, ...]
    training_start: str
    training_end: str
    row_count: int


@dataclass(frozen=True)
class TrainedModel:
    estimator: Any
    metadata: TrainingMetadata


class ModelTrainer(Protocol):
    def fit(self, features: pd.DataFrame, target: pd.Series) -> TrainedModel: ...


class ResearchModelTrainingDisabled:
    """Intentional v1 guardrail against casually training a production filter."""

    def fit(self, features: pd.DataFrame, target: pd.Series) -> TrainedModel:
        raise NotImplementedError(
            "Model training is intentionally disabled in schema v1. Collect clean data, "
            "define chronological out-of-sample tests, and account for all execution costs first."
        )
