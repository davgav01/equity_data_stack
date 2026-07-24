from datetime import date
from pathlib import Path

import pandas as pd

from equity_data_stack.ingestion_log import IngestionLog


def test_ingestion_log_records_and_checks_complete(tmp_path: Path) -> None:
    log = IngestionLog(tmp_path)
    trading_day = date(2024, 1, 2)

    assert not log.is_complete(trading_day, "1d")

    log.record(trading_day, "1d", "started")
    assert not log.is_complete(trading_day, "1d")

    log.record(trading_day, "1d", "complete")
    assert log.is_complete(trading_day, "1d")


def test_ingestion_log_missing_dates(tmp_path: Path) -> None:
    log = IngestionLog(tmp_path)
    days = [date(2024, 1, 2), date(2024, 1, 3)]

    log.record(days[0], "1d", "complete")

    missing = log.missing_dates(days, "1d")

    assert missing == [days[1]]


def test_ingestion_log_writes_csv_mirror(tmp_path: Path) -> None:
    log = IngestionLog(tmp_path)

    log.record(date(2024, 1, 2), "1d", "complete")

    assert log.path.exists()
    assert log.csv_path.exists()
    parquet_df = pd.read_parquet(log.path)
    csv_df = pd.read_csv(log.csv_path)
    assert csv_df.to_dict("records") == parquet_df.to_dict("records")


def test_ingestion_log_latest_complete_date(tmp_path: Path) -> None:
    log = IngestionLog(tmp_path)

    log.record(date(2024, 1, 2), "1d", "complete")
    log.record(date(2024, 1, 3), "1d", "failed")
    log.record(date(2024, 1, 4), "1d", "complete")

    assert log.latest_complete_date("1d") == date(2024, 1, 4)
