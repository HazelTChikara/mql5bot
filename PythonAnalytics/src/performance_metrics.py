"""Core performance statistics for closed trades."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import inf, sqrt
from statistics import NormalDist

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PerformanceSummary:
    trade_count: int
    wins: int
    losses: int
    breakeven: int
    win_rate: float
    win_rate_ci_lower: float
    win_rate_ci_upper: float
    confidence_level: float
    average_win: float
    average_loss: float
    expectancy: float
    profit_factor: float
    net_profit: float
    maximum_drawdown_money: float
    maximum_drawdown_percent: float
    sharpe_ratio: float
    sortino_ratio: float
    average_r: float
    total_r: float
    average_mfe_points: float
    average_mae_points: float

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)


def closed_trades(trades: pd.DataFrame) -> pd.DataFrame:
    if "trade_event_type" not in trades:
        raise ValueError("trade_event_type column is required")
    return trades.loc[trades["trade_event_type"].eq("CLOSED")].copy()


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0.0:
        return inf if numerator > 0.0 else 0.0
    return numerator / denominator


def wilson_interval(successes: int, observations: int, confidence_level: float) -> tuple[float, float]:
    """Return a Wilson score interval for a binomial success rate."""

    if observations < 0 or successes < 0 or successes > observations:
        raise ValueError("successes and observations must define a valid binomial sample")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must be between zero and one")
    if observations == 0:
        return 0.0, 1.0

    z = NormalDist().inv_cdf(0.5 + confidence_level / 2.0)
    proportion = successes / observations
    denominator = 1.0 + z * z / observations
    center = (proportion + z * z / (2.0 * observations)) / denominator
    margin = z / denominator * sqrt(
        proportion * (1.0 - proportion) / observations
        + z * z / (4.0 * observations * observations)
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def calculate_performance(
    trades: pd.DataFrame,
    *,
    initial_equity: float = 10_000.0,
    annualization_factor: float = 252.0,
    confidence_level: float = 0.95,
) -> PerformanceSummary:
    """Calculate trade-level metrics after spread/slippage/commission are in P/L.

    Sharpe and Sortino use the exported R multiple per closed trade and a
    configurable square-root annualization convention. They are research metrics,
    not guarantees of future performance.
    """

    if initial_equity <= 0.0:
        raise ValueError("initial_equity must be positive")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must be between zero and one")
    frame = closed_trades(trades)
    profits = pd.to_numeric(frame.get("profit_loss_money"), errors="coerce").dropna()
    r_values = pd.to_numeric(frame.get("profit_loss_r"), errors="coerce").dropna()
    if profits.empty:
        return PerformanceSummary(
            trade_count=0,
            wins=0,
            losses=0,
            breakeven=0,
            win_rate=0.0,
            win_rate_ci_lower=0.0,
            win_rate_ci_upper=1.0,
            confidence_level=confidence_level,
            average_win=0.0,
            average_loss=0.0,
            expectancy=0.0,
            profit_factor=0.0,
            net_profit=0.0,
            maximum_drawdown_money=0.0,
            maximum_drawdown_percent=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            average_r=0.0,
            total_r=0.0,
            average_mfe_points=0.0,
            average_mae_points=0.0,
        )

    wins = profits[profits > 0.0]
    losses = profits[profits < 0.0]
    equity = initial_equity + profits.cumsum()
    equity_with_start = pd.concat([pd.Series([initial_equity]), equity], ignore_index=True)
    peaks = equity_with_start.cummax()
    drawdowns = peaks - equity_with_start
    drawdown_pct = drawdowns / peaks.replace(0.0, np.nan)

    r_std = float(r_values.std(ddof=1)) if len(r_values) > 1 else 0.0
    downside = r_values[r_values < 0.0]
    downside_std = float(downside.std(ddof=1)) if len(downside) > 1 else 0.0
    annualizer = sqrt(annualization_factor)
    mean_r = float(r_values.mean()) if len(r_values) else 0.0
    win_rate_ci_lower, win_rate_ci_upper = wilson_interval(
        len(wins), len(profits), confidence_level
    )

    return PerformanceSummary(
        trade_count=int(len(profits)),
        wins=int(len(wins)),
        losses=int(len(losses)),
        breakeven=int((profits == 0.0).sum()),
        win_rate=float(len(wins) / len(profits)),
        win_rate_ci_lower=win_rate_ci_lower,
        win_rate_ci_upper=win_rate_ci_upper,
        confidence_level=confidence_level,
        average_win=float(wins.mean()) if len(wins) else 0.0,
        average_loss=float(losses.mean()) if len(losses) else 0.0,
        expectancy=float(profits.mean()),
        profit_factor=_safe_ratio(float(wins.sum()), abs(float(losses.sum()))),
        net_profit=float(profits.sum()),
        maximum_drawdown_money=float(drawdowns.max()),
        maximum_drawdown_percent=float(drawdown_pct.max()) if drawdown_pct.notna().any() else 0.0,
        sharpe_ratio=mean_r / r_std * annualizer if r_std > 0.0 else 0.0,
        sortino_ratio=mean_r / downside_std * annualizer if downside_std > 0.0 else 0.0,
        average_r=mean_r,
        total_r=float(r_values.sum()) if len(r_values) else 0.0,
        average_mfe_points=float(
            pd.to_numeric(frame.get("maximum_favorable_excursion_points"), errors="coerce").mean()
        ),
        average_mae_points=float(
            pd.to_numeric(frame.get("maximum_adverse_excursion_points"), errors="coerce").mean()
        ),
    )
