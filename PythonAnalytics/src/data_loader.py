"""Load the three linked CSV streams emitted by MetaTrader 5."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .schema import (
    BOOLEAN_COLUMNS,
    DATETIME_COLUMNS,
    FILE_NAMES,
    NUMERIC_COLUMNS,
    REQUIRED_COLUMNS,
    TEXT_COLUMNS,
    Table,
)


@dataclass(frozen=True)
class AnalyticsDataset:
    snapshots: pd.DataFrame
    decisions: pd.DataFrame
    trades: pd.DataFrame

    def table(self, table: Table) -> pd.DataFrame:
        return {
            Table.MARKET_SNAPSHOTS: self.snapshots,
            Table.SIGNAL_DECISIONS: self.decisions,
            Table.TRADE_EVENTS: self.trades,
        }[table]


def _parse_boolean(series: pd.Series) -> pd.Series:
    normalized = series.astype("string").str.strip().str.lower()
    return normalized.map({"true": True, "false": False, "1": True, "0": False}).astype(
        "boolean"
    )


def load_table(path: str | Path, table: Table) -> pd.DataFrame:
    """Load one table while preserving malformed values as missing for validation."""

    frame = pd.read_csv(path, dtype="string", keep_default_na=False)
    for column in TEXT_COLUMNS[table]:
        if column in frame:
            frame[column] = frame[column].astype("string")
    for column in NUMERIC_COLUMNS[table]:
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in DATETIME_COLUMNS[table]:
        if column in frame:
            frame[column] = pd.to_datetime(frame[column], errors="coerce")
    for column in BOOLEAN_COLUMNS[table]:
        if column in frame:
            frame[column] = _parse_boolean(frame[column])
    return frame


def _empty_table(table: Table) -> pd.DataFrame:
    return pd.DataFrame(columns=REQUIRED_COLUMNS[table])


def load_export_directory(
    directory: str | Path, *, allow_missing_files: bool = False
) -> AnalyticsDataset:
    """Load a complete export directory.

    Missing files raise ``FileNotFoundError`` unless ``allow_missing_files`` is true;
    validation can then report the empty stream.
    """

    directory = Path(directory)
    loaded: dict[Table, pd.DataFrame] = {}
    for table, file_name in FILE_NAMES.items():
        path = directory / file_name
        if not path.exists():
            if not allow_missing_files:
                raise FileNotFoundError(f"Missing analytics table: {path}")
            loaded[table] = _empty_table(table)
            continue
        loaded[table] = load_table(path, table)

    return AnalyticsDataset(
        snapshots=loaded[Table.MARKET_SNAPSHOTS],
        decisions=loaded[Table.SIGNAL_DECISIONS],
        trades=loaded[Table.TRADE_EVENTS],
    )
