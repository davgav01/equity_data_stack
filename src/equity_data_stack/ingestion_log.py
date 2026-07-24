"""Ingestion log for resumable operations."""

import os
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

LOG_COLUMNS = ["date", "freq", "status", "updated_at"]


@dataclass
class IngestionLog:
    data_root: Path

    def __post_init__(self) -> None:
        self.data_root = Path(self.data_root)
        (self.data_root / "logs").mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self.data_root / "logs" / "ingestion_log.parquet"

    @property
    def csv_path(self) -> Path:
        return self.data_root / "logs" / "ingestion_log.csv"

    def load(self) -> pd.DataFrame:
        if not self.path.exists():
            return pd.DataFrame(columns=LOG_COLUMNS)
        return pd.read_parquet(self.path)

    def is_complete(self, trading_day: date, freq: str) -> bool:
        df = self.load()
        if df.empty:
            return False
        match = df[(df["date"] == trading_day.isoformat()) & (df["freq"] == freq)]
        return not match.empty and (match.iloc[-1]["status"] == "complete")

    def record(self, trading_day: date, freq: str, status: str) -> None:
        df = self.load()
        entry = {
            "date": trading_day.isoformat(),
            "freq": freq,
            "status": status,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        df = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)

        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        df.to_parquet(tmp_path, index=False)
        os.replace(tmp_path, self.path)
        self._write_csv_mirror(df)

    def missing_dates(self, trading_days: list[date], freq: str) -> list[date]:
        df = self.load()
        if df.empty:
            return trading_days

        complete = df[(df["freq"] == freq) & (df["status"] == "complete")]["date"]
        complete_set = set(complete.tolist())
        return [day for day in trading_days if day.isoformat() not in complete_set]

    def latest_complete_date(self, freq: str) -> date | None:
        df = self.load()
        if df.empty:
            return None

        complete = df[(df["freq"] == freq) & (df["status"] == "complete")]["date"]
        if complete.empty:
            return None
        return date.fromisoformat(str(complete.max()))

    def tail(self, limit: int = 50) -> pd.DataFrame:
        df = self.load()
        if limit <= 0:
            return df.iloc[0:0]
        return df.tail(limit)

    def _write_csv_mirror(self, df: pd.DataFrame) -> None:
        tmp_path = self.csv_path.with_suffix(self.csv_path.suffix + ".tmp")
        df.to_csv(tmp_path, index=False)
        os.replace(tmp_path, self.csv_path)
