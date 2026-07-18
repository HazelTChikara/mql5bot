from __future__ import annotations

import pandas as pd
from pandas.testing import assert_series_equal
import pytest

from src.data_loader import AnalyticsDataset
from src.feature_engineering import build_setup_features


def test_future_row_does_not_change_past_features(sample_dataset: AnalyticsDataset) -> None:
    original = build_setup_features(sample_dataset, rolling_window=3)
    future_snapshot = sample_dataset.snapshots.iloc[[-1]].copy()
    future_decision = sample_dataset.decisions.iloc[[-1]].copy()
    future_snapshot.loc[:, "setup_id"] = "EURUSD-future"
    future_decision.loc[:, "setup_id"] = "EURUSD-future"
    future_snapshot.loc[:, "timestamp"] = pd.Timestamp("2030-01-01")
    future_decision.loc[:, "timestamp"] = pd.Timestamp("2030-01-01")
    future_snapshot.loc[:, "broker_server_time"] = pd.Timestamp("2030-01-01")
    future_snapshot.loc[:, "atr_points"] = 10_000.0
    extended = AnalyticsDataset(
        snapshots=pd.concat([sample_dataset.snapshots, future_snapshot], ignore_index=True),
        decisions=pd.concat([sample_dataset.decisions, future_decision], ignore_index=True),
        trades=sample_dataset.trades,
    )
    with_future = build_setup_features(extended, rolling_window=3)
    columns = ["ema_slope", "atr_percentile", "spread_percentile", "recent_market_range"]
    for column in columns:
        assert_series_equal(
            original.set_index("setup_id")[column],
            with_future.set_index("setup_id").loc[original["setup_id"], column],
            check_names=False,
        )


def test_price_and_point_units_are_not_mixed(sample_dataset: AnalyticsDataset) -> None:
    features = build_setup_features(sample_dataset, rolling_window=3)
    first = features.iloc[0]
    assert first["inferred_symbol_point"] == pytest.approx(0.0001)
    assert first["ema_distance_points"] == pytest.approx(10.0)
    assert first["confirmation_range_points"] == pytest.approx(30.0)
    assert first["confirmation_upper_wick_ratio"] == pytest.approx(5.0 / 30.0)
    assert first["trend_strength"] == pytest.approx(1.0)
