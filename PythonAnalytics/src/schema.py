"""Versioned schema shared with ``MQL5/Include/AnalyticsExporter.mqh``."""

from __future__ import annotations

from enum import Enum

ANALYTICS_SCHEMA_VERSION = 1


class Table(str, Enum):
    MARKET_SNAPSHOTS = "market_snapshots"
    SIGNAL_DECISIONS = "signal_decisions"
    TRADE_EVENTS = "trade_events"


FILE_NAMES = {
    Table.MARKET_SNAPSHOTS: "market_snapshots_v1.csv",
    Table.SIGNAL_DECISIONS: "signal_decisions_v1.csv",
    Table.TRADE_EVENTS: "trade_events_v1.csv",
}

MARKET_SNAPSHOT_COLUMNS = [
    "analytics_schema_version",
    "event_type",
    "setup_id",
    "timestamp",
    "symbol",
    "broker_server_time",
    "entry_timeframe",
    "trend_timeframe",
    "bid",
    "ask",
    "spread_points",
    "bar_open",
    "bar_high",
    "bar_low",
    "bar_close",
    "tick_volume",
    "atr_points",
    "fast_ema",
    "slow_ema",
    "trend_classification",
    "previous_day_high",
    "previous_day_low",
    "asian_session_high",
    "asian_session_low",
    "detected_swing_high",
    "detected_swing_low",
    "session_classification",
]

SIGNAL_DECISION_COLUMNS = [
    "analytics_schema_version",
    "event_type",
    "setup_id",
    "timestamp",
    "symbol",
    "liquidity_level_type",
    "liquidity_level_price",
    "sweep_direction",
    "sweep_extreme",
    "sweep_confirmation_time",
    "bos_direction",
    "broken_structure_level",
    "retest_price",
    "retest_distance_points",
    "confirmation_open",
    "confirmation_high",
    "confirmation_low",
    "confirmation_close",
    "confirmation_body_points",
    "confirmation_upper_wick_points",
    "confirmation_lower_wick_points",
    "confirmation_bullish",
    "proposed_entry_price",
    "proposed_stop_loss_price",
    "proposed_take_profit_price",
    "risk_points",
    "reward_to_risk_ratio",
    "calculated_position_size",
    "strategy_state",
    "signal_accepted",
    "rejection_reason",
    "external_available",
    "external_quality_score",
    "external_model_version",
    "external_decision",
    "external_explanation",
    "external_generated_at",
    "external_decision_applied",
    "applied_risk_multiplier",
]

TRADE_EVENT_COLUMNS = [
    "analytics_schema_version",
    "event_type",
    "setup_id",
    "timestamp",
    "symbol",
    "trade_ticket",
    "trade_event_type",
    "final_trade_result",
    "profit_loss_money",
    "profit_loss_r",
    "maximum_favorable_excursion_points",
    "maximum_adverse_excursion_points",
    "slippage_points",
    "holding_duration_seconds",
    "exit_reason",
    "entry_price",
    "exit_price",
    "volume",
]

REQUIRED_COLUMNS = {
    Table.MARKET_SNAPSHOTS: MARKET_SNAPSHOT_COLUMNS,
    Table.SIGNAL_DECISIONS: SIGNAL_DECISION_COLUMNS,
    Table.TRADE_EVENTS: TRADE_EVENT_COLUMNS,
}

EXPECTED_EVENT_TYPE = {
    Table.MARKET_SNAPSHOTS: "MARKET_SNAPSHOT",
    Table.SIGNAL_DECISIONS: "SIGNAL_DECISION",
    Table.TRADE_EVENTS: "TRADE_EVENT",
}

DATETIME_COLUMNS = {
    Table.MARKET_SNAPSHOTS: ["timestamp", "broker_server_time"],
    Table.SIGNAL_DECISIONS: [
        "timestamp",
        "sweep_confirmation_time",
        "external_generated_at",
    ],
    Table.TRADE_EVENTS: ["timestamp"],
}

BOOLEAN_COLUMNS = {
    Table.MARKET_SNAPSHOTS: [],
    Table.SIGNAL_DECISIONS: [
        "confirmation_bullish",
        "signal_accepted",
        "external_available",
        "external_decision_applied",
    ],
    Table.TRADE_EVENTS: [],
}

TEXT_COLUMNS = {
    Table.MARKET_SNAPSHOTS: [
        "event_type",
        "setup_id",
        "symbol",
        "entry_timeframe",
        "trend_timeframe",
        "trend_classification",
        "session_classification",
    ],
    Table.SIGNAL_DECISIONS: [
        "event_type",
        "setup_id",
        "symbol",
        "liquidity_level_type",
        "sweep_direction",
        "bos_direction",
        "strategy_state",
        "rejection_reason",
        "external_model_version",
        "external_decision",
        "external_explanation",
    ],
    Table.TRADE_EVENTS: [
        "event_type",
        "setup_id",
        "symbol",
        "trade_event_type",
        "final_trade_result",
        "exit_reason",
    ],
}

NUMERIC_COLUMNS = {
    table: [
        column
        for column in columns
        if column
        not in set(DATETIME_COLUMNS[table])
        | set(BOOLEAN_COLUMNS[table])
        | set(TEXT_COLUMNS[table])
    ]
    for table, columns in REQUIRED_COLUMNS.items()
}

# Empty timestamps are intentional when an optional event has not occurred.
NULLABLE_DATETIME_COLUMNS = {
    Table.MARKET_SNAPSHOTS: set(),
    Table.SIGNAL_DECISIONS: {"sweep_confirmation_time", "external_generated_at"},
    Table.TRADE_EVENTS: set(),
}

VALID_EXTERNAL_DECISIONS = {"APPROVE", "REJECT", "REDUCE_RISK", "NO_RESPONSE"}
VALID_TRADE_RESULTS = {"WIN", "LOSS", "BREAKEVEN", "OPEN", "NOT_APPLICABLE"}
