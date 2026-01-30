from datetime import date
from pathlib import Path

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
