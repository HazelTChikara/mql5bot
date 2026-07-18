"""Segment closed-trade performance by decision-time context."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .data_loader import AnalyticsDataset
from .performance_metrics import calculate_performance, closed_trades


def _tercile_bucket(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    percentiles = numeric.rank(method="average", pct=True)
    labels = np.select(
        [percentiles <= 1.0 / 3.0, percentiles <= 2.0 / 3.0],
        ["LOW", "MEDIUM"],
        default="HIGH",
    )
    result = pd.Series(labels, index=series.index, dtype="string")
    result[numeric.isna()] = "UNKNOWN"
    if numeric.nunique(dropna=True) <= 1:
        result[numeric.notna()] = "MEDIUM"
    return result


def build_trade_context(dataset: AnalyticsDataset) -> pd.DataFrame:
    trades = closed_trades(dataset.trades)
    decisions = dataset.decisions.copy()
    snapshots = dataset.snapshots.copy()
    context = trades.merge(
        decisions,
        on=["setup_id", "symbol"],
        how="left",
        suffixes=("_trade", "_decision"),
        validate="many_to_one",
    ).merge(
        snapshots,
        on=["setup_id", "symbol"],
        how="left",
        suffixes=("", "_snapshot"),
        validate="many_to_one",
    )
    trade_time = pd.to_datetime(context["timestamp_trade"], errors="coerce")
    context["day_of_week"] = trade_time.dt.day_name()
    context["direction"] = np.select(
        [context["bos_direction"].eq("UP"), context["bos_direction"].eq("DOWN")],
        ["LONG", "SHORT"],
        default="UNKNOWN",
    )
    if context["atr_points"].notna().any():
        context["volatility_level"] = _tercile_bucket(context["atr_points"])
    else:
        context["volatility_level"] = "UNKNOWN"
    if context["spread_points"].notna().any():
        context["spread_bucket"] = _tercile_bucket(context["spread_points"])
    else:
        context["spread_bucket"] = "UNKNOWN"
    context["market_regime"] = context["trend_classification"]
    return context


def performance_by(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    if column not in frame:
        raise ValueError(f"Unknown grouping column: {column}")
    rows: list[dict[str, object]] = []
    for label, group in frame.groupby(column, dropna=False, observed=True):
        summary = calculate_performance(group)
        rows.append({column: label, **summary.to_dict()})
    return pd.DataFrame(rows)


def standard_breakdowns(dataset: AnalyticsDataset) -> dict[str, pd.DataFrame]:
    context = build_trade_context(dataset)
    dimensions = [
        "session_classification",
        "day_of_week",
        "market_regime",
        "volatility_level",
        "spread_bucket",
        "liquidity_level_type",
        "direction",
    ]
    return {dimension: performance_by(context, dimension) for dimension in dimensions}
