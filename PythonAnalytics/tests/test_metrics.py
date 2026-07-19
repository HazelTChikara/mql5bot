from __future__ import annotations

import pytest

from src.data_loader import AnalyticsDataset
from src.performance_metrics import calculate_performance, wilson_interval


def test_core_performance_metrics(sample_dataset: AnalyticsDataset) -> None:
    result = calculate_performance(sample_dataset.trades, initial_equity=1_000.0)
    assert result.trade_count == 4
    assert result.wins == 2
    assert result.losses == 1
    assert result.breakeven == 1
    assert result.win_rate == pytest.approx(0.5)
    assert result.win_rate_ci_lower == pytest.approx(0.15003899)
    assert result.win_rate_ci_upper == pytest.approx(0.84996101)
    assert result.confidence_level == pytest.approx(0.95)
    assert result.average_win == pytest.approx(125.0)
    assert result.average_loss == pytest.approx(-50.0)
    assert result.expectancy == pytest.approx(50.0)
    assert result.profit_factor == pytest.approx(5.0)
    assert result.net_profit == pytest.approx(200.0)
    assert result.maximum_drawdown_money == pytest.approx(50.0)
    assert result.total_r == pytest.approx(2.0)


def test_wilson_interval_narrows_with_more_evidence() -> None:
    small = wilson_interval(5, 10, 0.95)
    large = wilson_interval(50, 100, 0.95)
    assert large[1] - large[0] < small[1] - small[0]


def test_invalid_confidence_level_is_rejected(sample_dataset: AnalyticsDataset) -> None:
    with pytest.raises(ValueError, match="confidence_level"):
        calculate_performance(sample_dataset.trades, confidence_level=1.0)
