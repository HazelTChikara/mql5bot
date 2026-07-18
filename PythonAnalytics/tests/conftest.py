from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from src.data_loader import AnalyticsDataset


@pytest.fixture
def sample_dataset() -> AnalyticsDataset:
    timestamps = pd.date_range("2026-01-05 08:00:00", periods=4, freq="15min")
    setup_ids = [f"EURUSD-{index}" for index in range(4)]
    snapshots = pd.DataFrame(
        {
            "analytics_schema_version": [1] * 4,
            "event_type": ["MARKET_SNAPSHOT"] * 4,
            "setup_id": setup_ids,
            "timestamp": timestamps,
            "symbol": ["EURUSD"] * 4,
            "broker_server_time": timestamps + pd.Timedelta(seconds=1),
            "entry_timeframe": ["PERIOD_M15"] * 4,
            "trend_timeframe": ["PERIOD_H1"] * 4,
            "bid": [1.1000, 1.1010, 1.1020, 1.1030],
            "ask": [1.1002, 1.1012, 1.1022, 1.1032],
            "spread_points": [2.0, 2.1, 1.9, 2.2],
            "bar_open": [1.0990, 1.1000, 1.1010, 1.1020],
            "bar_high": [1.1010, 1.1020, 1.1030, 1.1040],
            "bar_low": [1.0980, 1.0990, 1.1000, 1.1010],
            "bar_close": [1.1000, 1.1010, 1.1020, 1.1030],
            "tick_volume": [100, 110, 120, 130],
            "atr_points": [10.0, 11.0, 12.0, 13.0],
            "fast_ema": [1.1000, 1.1005, 1.1010, 1.1015],
            "slow_ema": [1.0990, 1.0995, 1.1000, 1.1005],
            "trend_classification": ["BULLISH"] * 4,
            "previous_day_high": [1.1100] * 4,
            "previous_day_low": [1.0900] * 4,
            "asian_session_high": [1.1050] * 4,
            "asian_session_low": [1.0950] * 4,
            "detected_swing_high": [1.1060] * 4,
            "detected_swing_low": [1.0960] * 4,
            "session_classification": ["LONDON"] * 4,
        }
    )
    decisions = pd.DataFrame(
        {
            "analytics_schema_version": [1] * 4,
            "event_type": ["SIGNAL_DECISION"] * 4,
            "setup_id": setup_ids,
            "timestamp": timestamps,
            "symbol": ["EURUSD"] * 4,
            "liquidity_level_type": ["RECENT_SWING"] * 4,
            "liquidity_level_price": [1.0990, 1.1000, 1.1010, 1.1020],
            "sweep_direction": ["NONE"] * 4,
            "sweep_extreme": [0.0] * 4,
            "sweep_confirmation_time": [pd.NaT] * 4,
            "bos_direction": ["UP"] * 4,
            "broken_structure_level": [1.0990, 1.1000, 1.1010, 1.1020],
            "retest_price": [0.0] * 4,
            "retest_distance_points": [0.0] * 4,
            "confirmation_open": [1.0990, 1.1000, 1.1010, 1.1020],
            "confirmation_high": [1.1010, 1.1020, 1.1030, 1.1040],
            "confirmation_low": [1.0980, 1.0990, 1.1000, 1.1010],
            "confirmation_close": [1.1000, 1.1010, 1.1020, 1.1030],
            "confirmation_body_points": [10.0] * 4,
            "confirmation_upper_wick_points": [5.0] * 4,
            "confirmation_lower_wick_points": [5.0] * 4,
            "confirmation_bullish": [True] * 4,
            "proposed_entry_price": [1.1002, 1.1012, 1.1022, 1.1032],
            "proposed_stop_loss_price": [1.0992, 1.1002, 1.1012, 1.1022],
            "proposed_take_profit_price": [1.1022, 1.1032, 1.1042, 1.1052],
            "risk_points": [10.0] * 4,
            "reward_to_risk_ratio": [2.0] * 4,
            "calculated_position_size": [0.1] * 4,
            "strategy_state": ["RULE_ACCEPTED"] * 4,
            "signal_accepted": [True] * 4,
            "rejection_reason": [""] * 4,
            "external_available": [False] * 4,
            "external_quality_score": [0.0] * 4,
            "external_model_version": [""] * 4,
            "external_decision": ["NO_RESPONSE"] * 4,
            "external_explanation": ["not requested"] * 4,
            "external_generated_at": [pd.NaT] * 4,
            "external_decision_applied": [False] * 4,
            "applied_risk_multiplier": [1.0] * 4,
        }
    )
    trades = pd.DataFrame(
        {
            "analytics_schema_version": [1] * 4,
            "event_type": ["TRADE_EVENT"] * 4,
            "setup_id": setup_ids,
            "timestamp": timestamps + pd.Timedelta(hours=1),
            "symbol": ["EURUSD"] * 4,
            "trade_ticket": [101, 102, 103, 104],
            "trade_event_type": ["CLOSED"] * 4,
            "final_trade_result": ["WIN", "LOSS", "WIN", "BREAKEVEN"],
            "profit_loss_money": [100.0, -50.0, 150.0, 0.0],
            "profit_loss_r": [1.0, -0.5, 1.5, 0.0],
            "maximum_favorable_excursion_points": [15.0, 5.0, 20.0, 4.0],
            "maximum_adverse_excursion_points": [3.0, 10.0, 2.0, 4.0],
            "slippage_points": [0.1, 0.2, 0.1, 0.0],
            "holding_duration_seconds": [3600, 1800, 5400, 900],
            "exit_reason": ["TAKE_PROFIT", "STOP_LOSS", "EXPERT", "EXPERT"],
            "entry_price": [1.1002, 1.1012, 1.1022, 1.1032],
            "exit_price": [1.1022, 1.1002, 1.1052, 1.1032],
            "volume": [0.1] * 4,
        }
    )
    return AnalyticsDataset(snapshots=snapshots, decisions=decisions, trades=trades)
