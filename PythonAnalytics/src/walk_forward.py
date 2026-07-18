"""Chronological walk-forward split and evaluation primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, Iterator, TypeVar

import pandas as pd

ModelT = TypeVar("ModelT")


@dataclass(frozen=True)
class WalkForwardSplit:
    fold: int
    train: pd.DataFrame
    test: pd.DataFrame


@dataclass(frozen=True)
class WalkForwardResult(Generic[ModelT]):
    fold: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    model: ModelT
    metrics: dict[str, float]


def iter_walk_forward(
    frame: pd.DataFrame,
    *,
    timestamp_column: str,
    train_size: int,
    test_size: int,
    step_size: int | None = None,
    expanding: bool = True,
) -> Iterator[WalkForwardSplit]:
    if min(train_size, test_size) <= 0:
        raise ValueError("train_size and test_size must be positive")
    step_size = test_size if step_size is None else step_size
    if step_size <= 0:
        raise ValueError("step_size must be positive")
    ordered = frame.sort_values(timestamp_column).reset_index(drop=True)
    train_start = 0
    train_end = train_size
    fold = 0
    while train_end + test_size <= len(ordered):
        yield WalkForwardSplit(
            fold=fold,
            train=ordered.iloc[train_start:train_end].copy(),
            test=ordered.iloc[train_end : train_end + test_size].copy(),
        )
        fold += 1
        train_end += step_size
        if not expanding:
            train_start += step_size


def run_walk_forward(
    frame: pd.DataFrame,
    *,
    timestamp_column: str,
    train_size: int,
    test_size: int,
    fit: Callable[[pd.DataFrame], ModelT],
    evaluate: Callable[[ModelT, pd.DataFrame], dict[str, float]],
    step_size: int | None = None,
    expanding: bool = True,
) -> list[WalkForwardResult[ModelT]]:
    results: list[WalkForwardResult[ModelT]] = []
    for split in iter_walk_forward(
        frame,
        timestamp_column=timestamp_column,
        train_size=train_size,
        test_size=test_size,
        step_size=step_size,
        expanding=expanding,
    ):
        model = fit(split.train)
        results.append(
            WalkForwardResult(
                fold=split.fold,
                train_start=split.train[timestamp_column].min(),
                train_end=split.train[timestamp_column].max(),
                test_start=split.test[timestamp_column].min(),
                test_end=split.test[timestamp_column].max(),
                model=model,
                metrics=evaluate(model, split.test),
            )
        )
    return results
