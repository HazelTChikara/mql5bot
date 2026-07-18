"""Bootstrap simulations of closed-trade paths."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .performance_metrics import closed_trades


@dataclass(frozen=True)
class MonteCarloSummary:
    simulations: int
    trades_per_simulation: int
    ending_equity_percentiles: dict[int, float]
    max_drawdown_percentiles: dict[int, float]
    probability_of_loss: float


def simulate_trade_paths(
    trades: pd.DataFrame,
    *,
    simulations: int = 5_000,
    initial_equity: float = 10_000.0,
    seed: int | None = None,
) -> tuple[np.ndarray, MonteCarloSummary]:
    if simulations <= 0 or initial_equity <= 0.0:
        raise ValueError("simulations and initial_equity must be positive")
    profits = pd.to_numeric(
        closed_trades(trades)["profit_loss_money"], errors="coerce"
    ).dropna().to_numpy(dtype=float)
    if len(profits) == 0:
        raise ValueError("At least one closed trade is required")

    rng = np.random.default_rng(seed)
    samples = rng.choice(profits, size=(simulations, len(profits)), replace=True)
    paths = initial_equity + np.cumsum(samples, axis=1)
    paths_with_start = np.concatenate(
        [np.full((simulations, 1), initial_equity), paths], axis=1
    )
    peaks = np.maximum.accumulate(paths_with_start, axis=1)
    drawdowns = peaks - paths_with_start
    maximum_drawdowns = drawdowns.max(axis=1)
    ending = paths[:, -1]
    percentiles = [5, 25, 50, 75, 95]
    summary = MonteCarloSummary(
        simulations=simulations,
        trades_per_simulation=len(profits),
        ending_equity_percentiles={
            p: float(np.percentile(ending, p)) for p in percentiles
        },
        max_drawdown_percentiles={
            p: float(np.percentile(maximum_drawdowns, p)) for p in percentiles
        },
        probability_of_loss=float(np.mean(ending < initial_equity)),
    )
    return paths_with_start, summary
