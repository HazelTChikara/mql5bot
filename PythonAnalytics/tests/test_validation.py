from __future__ import annotations

from src.data_loader import AnalyticsDataset
from src.validation import validate_dataset


def test_valid_dataset_has_no_errors(sample_dataset: AnalyticsDataset) -> None:
    report = validate_dataset(sample_dataset)
    assert report.is_valid
    assert report.errors == []
    assert report.warnings == []


def test_duplicate_and_malformed_records_are_detected(sample_dataset: AnalyticsDataset) -> None:
    decisions = sample_dataset.decisions.copy()
    decisions.loc[1, "setup_id"] = decisions.loc[0, "setup_id"]
    snapshots = sample_dataset.snapshots.copy()
    snapshots.loc[2, "spread_points"] = float("nan")
    report = validate_dataset(
        AnalyticsDataset(snapshots=snapshots, decisions=decisions, trades=sample_dataset.trades)
    )
    codes = {issue.code for issue in report.errors}
    assert "DUPLICATE_RECORD" in codes
    assert "MALFORMED_NUMERIC" in codes


def test_risk_multiplier_cannot_increase_risk(sample_dataset: AnalyticsDataset) -> None:
    decisions = sample_dataset.decisions.copy()
    decisions.loc[0, "applied_risk_multiplier"] = 1.1
    report = validate_dataset(
        AnalyticsDataset(
            snapshots=sample_dataset.snapshots,
            decisions=decisions,
            trades=sample_dataset.trades,
        )
    )
    assert any(issue.code == "RISK_MULTIPLIER" for issue in report.errors)


def test_open_trade_without_close_is_reported(sample_dataset: AnalyticsDataset) -> None:
    trades = sample_dataset.trades.copy()
    trades.loc[0, "trade_event_type"] = "OPENED"
    trades.loc[0, "final_trade_result"] = "OPEN"
    report = validate_dataset(
        AnalyticsDataset(
            snapshots=sample_dataset.snapshots,
            decisions=sample_dataset.decisions,
            trades=trades,
        )
    )
    assert any(issue.code == "UNCLOSED_TRADE" for issue in report.warnings)
