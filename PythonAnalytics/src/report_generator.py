"""Generate a portable Markdown report and optional equity/drawdown chart."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .data_loader import AnalyticsDataset
from .performance_metrics import calculate_performance, closed_trades
from .trade_analysis import standard_breakdowns
from .validation import validate_dataset


def generate_markdown_report(
    dataset: AnalyticsDataset,
    output_path: str | Path,
    *,
    initial_equity: float = 10_000.0,
    confidence_level: float = 0.95,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    validation = validate_dataset(dataset)
    summary = calculate_performance(
        dataset.trades,
        initial_equity=initial_equity,
        confidence_level=confidence_level,
    )
    lines = [
        "# MT5 Analytics Report",
        "",
        "## Data quality",
        "",
        f"- Valid: {'yes' if validation.is_valid else 'no'}",
        f"- Errors: {len(validation.errors)}",
        f"- Warnings: {len(validation.warnings)}",
        "",
        "## Overall performance",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for name, value in summary.to_dict().items():
        lines.append(f"| {name.replace('_', ' ').title()} | {value:.4f} |" if isinstance(value, float) else f"| {name.replace('_', ' ').title()} | {value} |")

    if validation.is_valid:
        for dimension, breakdown in standard_breakdowns(dataset).items():
            lines.extend(["", f"## By {dimension.replace('_', ' ')}", "", breakdown.to_markdown(index=False)])
    lines.extend(
        [
            "",
            "> Results are descriptive, not a profitability guarantee. Use chronological",
            "> out-of-sample testing and include spread, slippage, commissions, and delays.",
            "",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def generate_equity_chart(
    trades: pd.DataFrame,
    output_path: str | Path,
    *,
    initial_equity: float = 10_000.0,
) -> Path:
    import matplotlib.pyplot as plt

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    closed = closed_trades(trades)
    profits = pd.to_numeric(closed["profit_loss_money"], errors="coerce").dropna()
    equity = pd.concat(
        [pd.Series([initial_equity]), initial_equity + profits.cumsum()], ignore_index=True
    )
    peak = equity.cummax()
    drawdown = equity - peak
    figure, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    axes[0].plot(equity.to_numpy())
    axes[0].set_title("Equity by closed trade")
    axes[0].set_ylabel("Equity")
    axes[1].fill_between(range(len(drawdown)), drawdown.to_numpy(), 0.0)
    axes[1].set_title("Drawdown")
    axes[1].set_xlabel("Closed trade number")
    axes[1].set_ylabel("Money")
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)
    return output_path
