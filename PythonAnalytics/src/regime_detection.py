"""Transparent baseline regime labels; replace only after out-of-sample validation."""

from __future__ import annotations

import numpy as np
import pandas as pd


def classify_rule_based_regime(
    features: pd.DataFrame,
    *,
    trend_strength_threshold: float = 0.25,
    high_volatility_percentile: float = 0.8,
) -> pd.Series:
    required = {"ema_distance", "trend_strength", "atr_percentile"}
    missing = required - set(features.columns)
    if missing:
        raise ValueError(f"Missing regime features: {sorted(missing)}")
    return pd.Series(
        np.select(
            [
                features["atr_percentile"] >= high_volatility_percentile,
                (features["ema_distance"] > 0)
                & (features["trend_strength"] >= trend_strength_threshold),
                (features["ema_distance"] < 0)
                & (features["trend_strength"] >= trend_strength_threshold),
            ],
            ["HIGH_VOLATILITY", "TREND_UP", "TREND_DOWN"],
            default="RANGE",
        ),
        index=features.index,
        name="market_regime",
        dtype="string",
    )
