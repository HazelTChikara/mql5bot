from __future__ import annotations

import pytest

from src.data_loader import AnalyticsDataset
from src.performance_metrics import calculate_performance


def test_core_performance_metrics(sample_dataset: AnalyticsDataset) -> None:
    result = calculate_performance(sample_dataset.trades, initial_equity=1_000.0)
    assert result.trade_count == 4
    assert result.wins == 2
    assert result.losses == 1
    assert result.breakeven == 1
    assert result.win_rate == pytest.approx(0.5)
    assert result.average_win == pytest.approx(125.0)
    assert result.average_loss == pytest.approx(-50.0)
    assert result.expectancy == pytest.approx(50.0)
    assert result.profit_factor == pytest.approx(5.0)
    assert result.net_profit == pytest.approx(200.0)
    assert result.maximum_drawdown_money == pytest.approx(50.0)
    assert result.total_r == pytest.approx(2.0)
