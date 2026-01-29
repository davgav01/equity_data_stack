"""Storage manager for parquet-backed data lake."""

import logging
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

REQUIRED_BAR_COLUMNS = {
    "timestamp",
    "symbol",
    "open",
    "high",
    "low",
    "close",
    "vwap",
    "volume",
    "n_trades",
}


@dataclass
class StorageManager:
    data_root: Path

    def __post_init__(self) -> None:
        """Ensure base data directories exist under data_root."""
        self.data_root = Path(self.data_root)
        (self.data_root / "bars").mkdir(parents=True, exist_ok=True)
        (self.data_root / "corporate_actions").mkdir(parents=True, exist_ok=True)
        (self.data_root / "logs").mkdir(parents=True, exist_ok=True)
        (self.data_root / "universe" / "snapshots").mkdir(parents=True, exist_ok=True)

    def write_bars(self, df: pd.DataFrame, freq: str) -> list[Path]:
        """Write bars to partitioned parquet files."""
        df = self._normalize_bars(df)
        paths: list[Path] = []

        if freq == "1d":
            for year, year_df in df.groupby(df["timestamp"].dt.year):
                path = (
                    self.data_root
                    / "bars"
                    / f"freq={freq}"
                    / f"year={year}"
                    / f"{year}.parquet"
                )
                self._write_or_merge(path, year_df)
                paths.append(path)
        elif freq == "1min":
            for day, day_df in df.groupby(df["timestamp"].dt.date):
                year = day.strftime("%Y")
                month = day.strftime("%m")
                path = (
                    self.data_root
                    / "bars"
                    / f"freq={freq}"
                    / f"year={year}"
                    / f"month={month}"
                    / f"day={day.isoformat()}.parquet"
                )
                self._write_or_merge(path, day_df)
                paths.append(path)
        else:
            raise ValueError(f"Unsupported frequency: {freq}")

        return paths

    def write_security_master(self, df: pd.DataFrame) -> Path:
        """Write or merge the security master table."""
        path = self.data_root / "security_master.parquet"
        self._write_or_merge(path, df, dedupe_on=["symbol"])
        return path

    def write_splits(self, df: pd.DataFrame) -> Path:
        """Write or merge split events."""
        path = self.data_root / "corporate_actions" / "splits.parquet"
        self._write_or_merge(
            path, df, dedupe_on=_dedupe_columns(df, ["symbol", "execution_date"])
        )
        return path

    def write_dividends(self, df: pd.DataFrame) -> Path:
        """Write or merge dividend events."""
        path = self.data_root / "corporate_actions" / "dividends.parquet"
        self._write_or_merge(
            path, df, dedupe_on=_dedupe_columns(df, ["symbol", "ex_dividend_date"])
        )
        return path

    def write_universe_snapshot(
        self, snapshot_df: pd.DataFrame, snapshot_date: date
    ) -> Path:
        """Write or merge a single-day universe snapshot."""
        path = (
            self.data_root
            / "universe"
            / "snapshots"
            / f"date={snapshot_date.isoformat()}.parquet"
        )
        self._write_or_merge(path, snapshot_df, dedupe_on=["symbol"])
        return path

    def _normalize_bars(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate bar schema, enforce UTC timestamps, and dedupe."""
        missing = REQUIRED_BAR_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(f"Missing required bar columns: {sorted(missing)}")

        df = df.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.drop_duplicates(subset=["timestamp", "symbol"])
        df = df.sort_values(["timestamp", "symbol"])
        return df

    def _write_or_merge(
        self,
        path: Path,
        df: pd.DataFrame,
        dedupe_on: list[str] | None = None,
    ) -> None:
        """Merge with existing parquet (if any) and atomically replace."""
        path.parent.mkdir(parents=True, exist_ok=True)
        dedupe_on = dedupe_on or ["timestamp", "symbol"]

        if path.exists():
            existing = pd.read_parquet(path)
            combined = pd.concat([existing, df], ignore_index=True)
        else:
            combined = df

        combined = combined.drop_duplicates(subset=dedupe_on)

        tmp_path = path.with_suffix(path.suffix + ".tmp")
        combined.to_parquet(tmp_path, index=False)
        os.replace(tmp_path, path)


def _dedupe_columns(df: pd.DataFrame, preferred: list[str]) -> list[str]:
    """Pick dedupe columns based on available fields."""
    columns = [col for col in preferred if col in df.columns]
    if columns:
        return columns
    fallback = [
        col
        for col in ["symbol", "date", "execution_date", "ex_dividend_date"]
        if col in df.columns
    ]
    return fallback or list(df.columns)
