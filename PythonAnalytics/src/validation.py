"""Schema, record-quality, and cross-table validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

from .data_loader import AnalyticsDataset
from .schema import (
    ANALYTICS_SCHEMA_VERSION,
    BOOLEAN_COLUMNS,
    DATETIME_COLUMNS,
    EXPECTED_EVENT_TYPE,
    NULLABLE_DATETIME_COLUMNS,
    NUMERIC_COLUMNS,
    REQUIRED_COLUMNS,
    VALID_EXTERNAL_DECISIONS,
    VALID_TRADE_RESULTS,
    Table,
)


@dataclass(frozen=True)
class ValidationIssue:
    severity: Literal["error", "warning"]
    code: str
    table: str
    message: str
    row: int | None = None


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    def add(
        self,
        severity: Literal["error", "warning"],
        code: str,
        table: Table,
        message: str,
        row: int | None = None,
    ) -> None:
        self.issues.append(ValidationIssue(severity, code, table.value, message, row))


def _report_rows(
    report: ValidationReport,
    table: Table,
    mask: pd.Series,
    code: str,
    message: str,
    severity: Literal["error", "warning"] = "error",
) -> None:
    for row in mask[mask.fillna(False)].index.tolist():
        report.add(severity, code, table, message, int(row) if isinstance(row, int) else None)


def _validate_table(frame: pd.DataFrame, table: Table, report: ValidationReport) -> None:
    missing = [column for column in REQUIRED_COLUMNS[table] if column not in frame.columns]
    if missing:
        report.add("error", "MISSING_COLUMNS", table, f"Missing columns: {', '.join(missing)}")
        return
    if frame.empty:
        report.add("warning", "EMPTY_TABLE", table, "Table contains no records")
        return

    _report_rows(
        report,
        table,
        frame["analytics_schema_version"] != ANALYTICS_SCHEMA_VERSION,
        "SCHEMA_VERSION",
        f"Expected analytics_schema_version={ANALYTICS_SCHEMA_VERSION}",
    )
    _report_rows(
        report,
        table,
        frame["event_type"] != EXPECTED_EVENT_TYPE[table],
        "EVENT_TYPE",
        f"Expected event_type={EXPECTED_EVENT_TYPE[table]}",
    )
    _report_rows(
        report,
        table,
        frame["setup_id"].isna() | frame["setup_id"].astype("string").str.strip().eq(""),
        "MISSING_SETUP_ID",
        "setup_id is required",
    )
    _report_rows(
        report,
        table,
        frame["symbol"].isna() | frame["symbol"].astype("string").str.strip().eq(""),
        "MISSING_SYMBOL",
        "symbol is required",
    )

    for column in NUMERIC_COLUMNS[table]:
        _report_rows(
            report,
            table,
            frame[column].isna(),
            "MALFORMED_NUMERIC",
            f"{column} is missing or malformed",
        )
    for column in BOOLEAN_COLUMNS[table]:
        _report_rows(
            report,
            table,
            frame[column].isna(),
            "MALFORMED_BOOLEAN",
            f"{column} is missing or malformed",
        )
    for column in DATETIME_COLUMNS[table]:
        if column in NULLABLE_DATETIME_COLUMNS[table]:
            continue
        _report_rows(
            report,
            table,
            frame[column].isna(),
            "MALFORMED_TIMESTAMP",
            f"{column} is missing or malformed",
        )

    if table in {Table.MARKET_SNAPSHOTS, Table.SIGNAL_DECISIONS}:
        duplicate = frame["setup_id"].duplicated(keep=False)
    else:
        duplicate = frame.duplicated(
            subset=["setup_id", "trade_event_type", "timestamp"], keep=False
        )
    _report_rows(
        report,
        table,
        duplicate,
        "DUPLICATE_RECORD",
        "Duplicate analytics record",
    )


def validate_dataset(dataset: AnalyticsDataset) -> ValidationReport:
    report = ValidationReport()
    for table in Table:
        _validate_table(dataset.table(table), table, report)

    snapshots = dataset.snapshots
    decisions = dataset.decisions
    trades = dataset.trades
    if not snapshots.empty and not decisions.empty and "setup_id" in snapshots and "setup_id" in decisions:
        missing_snapshots = ~decisions["setup_id"].isin(set(snapshots["setup_id"].dropna()))
        _report_rows(
            report,
            Table.SIGNAL_DECISIONS,
            missing_snapshots,
            "ORPHAN_DECISION",
            "Decision has no matching market snapshot",
        )
    if not decisions.empty and not trades.empty and "setup_id" in decisions and "setup_id" in trades:
        missing_decisions = ~trades["setup_id"].isin(set(decisions["setup_id"].dropna()))
        _report_rows(
            report,
            Table.TRADE_EVENTS,
            missing_decisions,
            "ORPHAN_TRADE",
            "Trade event has no matching signal decision",
        )

    if not decisions.empty and set(REQUIRED_COLUMNS[Table.SIGNAL_DECISIONS]).issubset(decisions):
        _report_rows(
            report,
            Table.SIGNAL_DECISIONS,
            ~decisions["external_decision"].isin(VALID_EXTERNAL_DECISIONS),
            "EXTERNAL_DECISION",
            "Unknown external decision",
        )
        accepted_with_reason = decisions["signal_accepted"].eq(True) & decisions[
            "rejection_reason"
        ].astype("string").str.strip().ne("")
        _report_rows(
            report,
            Table.SIGNAL_DECISIONS,
            accepted_with_reason,
            "ACCEPTED_WITH_REJECTION_REASON",
            "Accepted signal should not have a rejection reason",
            "warning",
        )
        invalid_multiplier = (decisions["applied_risk_multiplier"] <= 0.0) | (
            decisions["applied_risk_multiplier"] > 1.0
        )
        _report_rows(
            report,
            Table.SIGNAL_DECISIONS,
            invalid_multiplier,
            "RISK_MULTIPLIER",
            "Applied risk multiplier must be in (0, 1]",
        )

    if not trades.empty and set(REQUIRED_COLUMNS[Table.TRADE_EVENTS]).issubset(trades):
        _report_rows(
            report,
            Table.TRADE_EVENTS,
            ~trades["final_trade_result"].isin(VALID_TRADE_RESULTS),
            "TRADE_RESULT",
            "Unknown final trade result",
        )
        closed = trades["trade_event_type"].eq("CLOSED")
        _report_rows(
            report,
            Table.TRADE_EVENTS,
            closed & (trades["trade_ticket"] <= 0),
            "CLOSED_WITHOUT_TICKET",
            "Closed trade must have a positive ticket",
        )
        _report_rows(
            report,
            Table.TRADE_EVENTS,
            closed & (trades["holding_duration_seconds"] < 0),
            "NEGATIVE_HOLDING_DURATION",
            "Holding duration cannot be negative",
        )
    return report
