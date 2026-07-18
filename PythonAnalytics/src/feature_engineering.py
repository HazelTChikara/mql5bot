"""Leakage-safe feature engineering using only current and earlier records."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .data_loader import AnalyticsDataset


def _rolling_last_percentile(series: pd.Series, window: int) -> pd.Series:
    def percentile(values: np.ndarray) -> float:
        if len(values) == 0 or np.isnan(values[-1]):
            return np.nan
        valid = values[~np.isnan(values)]
        if len(valid) == 0:
            return np.nan
        return float(np.count_nonzero(valid <= values[-1]) / len(valid))

    return series.rolling(window=window, min_periods=1).apply(percentile, raw=True)


def build_setup_features(
    dataset: AnalyticsDataset, *, rolling_window: int = 100
) -> pd.DataFrame:
    """Return one row per setup with no backward fill or future aggregation.

    Input is sorted by symbol and decision timestamp. Rolling features include the
    current closed-bar record and prior records only.
    """

    if rolling_window < 2:
        raise ValueError("rolling_window must be at least 2")
    snapshots = dataset.snapshots.copy()
    decisions = dataset.decisions.copy()
    merged = snapshots.merge(
        decisions,
        on=["setup_id", "symbol"],
        how="inner",
        suffixes=("_snapshot", "_decision"),
        validate="one_to_one",
    )
    timestamp_column = "timestamp_decision"
    merged = merged.sort_values(["symbol", timestamp_column, "setup_id"]).reset_index(drop=True)

    point_from_risk = (
        (merged["proposed_entry_price"] - merged["proposed_stop_loss_price"]).abs()
        / merged["risk_points"].replace(0.0, np.nan)
    )
    point_from_spread = (
        (merged["ask"] - merged["bid"]).abs()
        / merged["spread_points"].replace(0.0, np.nan)
    )
    merged["inferred_symbol_point"] = point_from_risk.fillna(point_from_spread)
    merged["ema_distance"] = merged["fast_ema"] - merged["slow_ema"]
    merged["ema_distance_points"] = (
        merged["ema_distance"] / merged["inferred_symbol_point"].replace(0.0, np.nan)
    )
    merged["ema_slope"] = merged.groupby("symbol", sort=False)["fast_ema"].diff()
    merged["atr_percentile"] = merged.groupby("symbol", sort=False)["atr_points"].transform(
        lambda series: _rolling_last_percentile(series, rolling_window)
    )
    merged["spread_percentile"] = merged.groupby("symbol", sort=False)[
        "spread_points"
    ].transform(lambda series: _rolling_last_percentile(series, rolling_window))
    merged["sweep_depth"] = (
        merged["sweep_extreme"] - merged["liquidity_level_price"]
    ).abs()
    merged["confirmation_range"] = merged["confirmation_high"] - merged["confirmation_low"]
    merged["confirmation_range_points"] = (
        merged["confirmation_range"] / merged["inferred_symbol_point"].replace(0.0, np.nan)
    )
    nonzero_range = merged["confirmation_range_points"].replace(0.0, np.nan)
    merged["sweep_wick_to_body_ratio"] = (
        merged[["confirmation_upper_wick_points", "confirmation_lower_wick_points"]].max(axis=1)
        / merged["confirmation_body_points"].replace(0.0, np.nan)
    )
    merged["confirmation_upper_wick_ratio"] = (
        merged["confirmation_upper_wick_points"] / nonzero_range
    )
    merged["confirmation_lower_wick_ratio"] = (
        merged["confirmation_lower_wick_points"] / nonzero_range
    )
    merged["distance_from_previous_day_high"] = (
        merged["bar_close"] - merged["previous_day_high"]
    )
    merged["distance_from_previous_day_low"] = (
        merged["bar_close"] - merged["previous_day_low"]
    )
    merged["distance_from_asian_high"] = merged["bar_close"] - merged["asian_session_high"]
    merged["distance_from_asian_low"] = merged["bar_close"] - merged["asian_session_low"]
    merged["bos_displacement"] = (
        merged["confirmation_close"] - merged["broken_structure_level"]
    ).abs()
    merged["retest_depth"] = merged["retest_distance_points"]
    merged["confirmation_body_size"] = merged["confirmation_body_points"]
    merged["time_of_day_minutes"] = (
        merged[timestamp_column].dt.hour * 60 + merged[timestamp_column].dt.minute
    )
    merged["day_of_week"] = merged[timestamp_column].dt.day_name()
    rolling_high = merged.groupby("symbol", sort=False)["bar_high"].transform(
        lambda series: series.rolling(rolling_window, min_periods=1).max()
    )
    rolling_low = merged.groupby("symbol", sort=False)["bar_low"].transform(
        lambda series: series.rolling(rolling_window, min_periods=1).min()
    )
    merged["recent_market_range"] = rolling_high - rolling_low
    merged["trend_strength"] = merged["ema_distance_points"].abs() / merged["atr_points"].replace(
        0.0, np.nan
    )
    merged["distance_to_nearest_structure"] = pd.concat(
        [
            (merged["bar_close"] - merged["detected_swing_high"]).abs(),
            (merged["bar_close"] - merged["detected_swing_low"]).abs(),
        ],
        axis=1,
    ).min(axis=1)
    return merged
