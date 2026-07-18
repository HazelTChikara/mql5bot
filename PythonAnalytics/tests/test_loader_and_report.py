from __future__ import annotations

from src.data_loader import AnalyticsDataset, load_export_directory
from src.report_generator import generate_markdown_report
from src.schema import FILE_NAMES, Table
from src.trade_analysis import standard_breakdowns
from src.validation import validate_dataset


def test_export_directory_round_trip(sample_dataset: AnalyticsDataset, tmp_path) -> None:
    tables = {
        Table.MARKET_SNAPSHOTS: sample_dataset.snapshots,
        Table.SIGNAL_DECISIONS: sample_dataset.decisions,
        Table.TRADE_EVENTS: sample_dataset.trades,
    }
    for table, frame in tables.items():
        frame.to_csv(tmp_path / FILE_NAMES[table], index=False)

    loaded = load_export_directory(tmp_path)
    assert len(loaded.snapshots) == 4
    assert len(loaded.decisions) == 4
    assert len(loaded.trades) == 4
    assert validate_dataset(loaded).is_valid


def test_markdown_report_contains_core_metrics(sample_dataset: AnalyticsDataset, tmp_path) -> None:
    path = generate_markdown_report(sample_dataset, tmp_path / "summary.md")
    content = path.read_text(encoding="utf-8")
    assert "# MT5 Analytics Report" in content
    assert "| Trade Count | 4 |" in content
    assert "## By session classification" in content


def test_identical_values_form_a_stable_middle_bucket(sample_dataset: AnalyticsDataset) -> None:
    snapshots = sample_dataset.snapshots.copy()
    snapshots["spread_points"] = 2.0
    snapshots["atr_points"] = 10.0
    dataset = AnalyticsDataset(snapshots, sample_dataset.decisions, sample_dataset.trades)
    breakdowns = standard_breakdowns(dataset)
    assert breakdowns["spread_bucket"]["spread_bucket"].tolist() == ["MEDIUM"]
    assert breakdowns["volatility_level"]["volatility_level"].tolist() == ["MEDIUM"]
