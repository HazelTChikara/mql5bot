# PythonAnalytics

This optional package validates and analyzes the version-1 CSV contract emitted by the MQL5 EA. It is not imported or called by MetaTrader 5. Deleting this folder does not prevent the EA from trading or backtesting.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

Copy an MT5 export set into `data/`, then load and validate it:

```python
from src.data_loader import load_export_directory
from src.validation import validate_dataset
from src.performance_metrics import calculate_performance

dataset = load_export_directory("data")
report = validate_dataset(dataset)
if not report.is_valid:
    for issue in report.errors:
        print(issue)
else:
    print(calculate_performance(dataset.trades).to_dict())
```

Generate an offline Markdown report after validation:

```python
from src.report_generator import generate_markdown_report

generate_markdown_report(dataset, "reports/summary.md")
```

## Modules

| Module | Version-1 responsibility |
|---|---|
| `schema.py` | Canonical filenames, columns, types, enums, and schema version. |
| `data_loader.py` | Loads all three CSV streams and normalizes datetimes, numerics, and booleans. |
| `validation.py` | Finds missing columns, invalid versions/types, malformed values, duplicates, orphan rows, invalid results, and risk multipliers above one. |
| `feature_engineering.py` | Computes decision-time features using only current and earlier closed-bar records. |
| `performance_metrics.py` | Win rate, wins/losses, expectancy, profit factor, drawdown, Sharpe, Sortino, R, MFE, and MAE. |
| `trade_analysis.py` | Breakdowns by session, weekday, regime, volatility, spread, liquidity-level type, and direction. |
| `walk_forward.py` | Strictly chronological rolling or expanding train/test splits and callback-based evaluation. |
| `monte_carlo.py` | Seeded bootstrap trade-path simulations and drawdown/ending-equity percentiles. |
| `regime_detection.py` | Transparent rule-based baseline regime labels. |
| `parameter_stability.py` | Parameter-surface and fold-to-fold stability diagnostics. |
| `model_training.py` | Future model interface; training is intentionally disabled in version 1. |
| `model_evaluation.py` | Basic accuracy, precision, recall, and Brier score for later binary models. |
| `report_generator.py` | Markdown summaries and optional equity/drawdown chart generation. |

## Leakage prevention

`build_setup_features` sorts records by symbol and decision timestamp. EMA slope uses a backward difference. ATR/spread percentiles and recent ranges use rolling windows containing the current closed record and historical records only. It never backward-fills, computes full-sample percentiles, or joins a final trade result into decision-time features.

Keep these rules when adding features:

- Use only data whose timestamp is no later than the setup decision.
- Fit scalers, encoders, selectors, regimes, and models on each training fold only.
- Never randomly shuffle time-series folds.
- Do not use final P/L, MFE, MAE, holding duration, or exit reason as entry features.
- Recompute rolling statistics inside each chronological research run.
- Preserve rejected setups; otherwise the dataset is selection-biased.

The version-1 placeholders leave room for EMA distance/slope, ATR and spread percentiles, sweep depth, wick/body ratios, distances from daily/Asian levels, BOS displacement, retest depth, candle shape, time/session/weekday, recent range, trend strength, structure distance, failed sweeps, and recent performance. Some require strategy-specific history that the demonstration EA does not yet calculate; add them only with timestamp-safe source data and a schema version change where necessary.

## Research guardrails

Performance numbers are descriptive. Validate on unseen chronological periods and include spread, slippage, commissions, and execution delays. A model should not be connected to `EXTERNAL_FILTER` until it improves an explicitly chosen out-of-sample objective without weakening tail risk or parameter stability.
