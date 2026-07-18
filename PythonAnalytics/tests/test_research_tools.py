from __future__ import annotations

import pytest

from src.data_loader import AnalyticsDataset
from src.monte_carlo import simulate_trade_paths
from src.walk_forward import iter_walk_forward


def test_monte_carlo_is_reproducible(sample_dataset: AnalyticsDataset) -> None:
    first_paths, first = simulate_trade_paths(sample_dataset.trades, simulations=50, seed=7)
    second_paths, second = simulate_trade_paths(sample_dataset.trades, simulations=50, seed=7)
    assert (first_paths == second_paths).all()
    assert first == second
    assert first.trades_per_simulation == 4


def test_walk_forward_never_overlaps_train_and_test(sample_dataset: AnalyticsDataset) -> None:
    splits = list(
        iter_walk_forward(
            sample_dataset.snapshots,
            timestamp_column="timestamp",
            train_size=2,
            test_size=1,
        )
    )
    assert len(splits) == 2
    for split in splits:
        assert split.train["timestamp"].max() < split.test["timestamp"].min()


def test_monte_carlo_requires_closed_trades(sample_dataset: AnalyticsDataset) -> None:
    trades = sample_dataset.trades.copy()
    trades["trade_event_type"] = "OPENED"
    with pytest.raises(ValueError, match="closed trade"):
        simulate_trade_paths(trades, simulations=10)
