"""Diagnostics for parameter surfaces and fold-to-fold instability."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class StabilitySummary:
    parameter: str
    best_value: float
    best_score: float
    median_score: float
    score_coefficient_of_variation: float
    neighboring_score_drop: float


def summarize_parameter_surface(
    results: pd.DataFrame,
    *,
    parameter_column: str,
    score_column: str,
) -> StabilitySummary:
    if parameter_column not in results or score_column not in results:
        raise ValueError("Parameter and score columns are required")
    ordered = results[[parameter_column, score_column]].dropna().sort_values(parameter_column)
    if ordered.empty:
        raise ValueError("No valid parameter results")
    scores = ordered[score_column].astype(float)
    best_position = int(np.argmax(scores.to_numpy()))
    best = ordered.iloc[best_position]
    neighbor_positions = [p for p in (best_position - 1, best_position + 1) if 0 <= p < len(ordered)]
    neighbor_mean = (
        float(ordered.iloc[neighbor_positions][score_column].mean())
        if neighbor_positions
        else float(best[score_column])
    )
    mean_abs = abs(float(scores.mean()))
    coefficient = float(scores.std(ddof=1) / mean_abs) if len(scores) > 1 and mean_abs > 0 else 0.0
    return StabilitySummary(
        parameter=parameter_column,
        best_value=float(best[parameter_column]),
        best_score=float(best[score_column]),
        median_score=float(scores.median()),
        score_coefficient_of_variation=coefficient,
        neighboring_score_drop=float(best[score_column]) - neighbor_mean,
    )


def fold_instability(
    fold_results: pd.DataFrame, *, parameter_columns: list[str]
) -> pd.DataFrame:
    missing = set(parameter_columns) - set(fold_results.columns)
    if missing:
        raise ValueError(f"Missing parameter columns: {sorted(missing)}")
    rows = []
    for column in parameter_columns:
        values = pd.to_numeric(fold_results[column], errors="coerce").dropna()
        rows.append(
            {
                "parameter": column,
                "fold_count": len(values),
                "mean": float(values.mean()) if len(values) else np.nan,
                "std": float(values.std(ddof=1)) if len(values) > 1 else 0.0,
                "min": float(values.min()) if len(values) else np.nan,
                "max": float(values.max()) if len(values) else np.nan,
            }
        )
    return pd.DataFrame(rows)
