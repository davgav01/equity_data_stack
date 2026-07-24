from datetime import date
from pathlib import Path

import pytest

from equity_data_stack.ingestion_log import IngestionLog
from equity_data_stack.update import build_update_windows, default_update_end


def test_build_update_windows_requires_start_without_history(tmp_path: Path) -> None:
    log = IngestionLog(tmp_path)

    with pytest.raises(ValueError, match="Pass --start"):
        build_update_windows(log, ["1d"], None, date(2024, 2, 6))


def test_build_update_windows_uses_fallback_start_without_history(
    tmp_path: Path,
) -> None:
    log = IngestionLog(tmp_path)

    windows = build_update_windows(
        log,
        ["1d"],
        date(2024, 2, 1),
        date(2024, 2, 6),
    )

    assert len(windows) == 1
    assert windows[0].start == date(2024, 2, 1)
    assert windows[0].end == date(2024, 2, 6)


def test_build_update_windows_advances_to_next_trading_day(tmp_path: Path) -> None:
    log = IngestionLog(tmp_path)
    log.record(date(2024, 2, 2), "1d", "complete")

    windows = build_update_windows(log, ["1d"], None, date(2024, 2, 6))

    assert len(windows) == 1
    assert windows[0].start == date(2024, 2, 5)


def test_build_update_windows_noops_when_current(tmp_path: Path) -> None:
    log = IngestionLog(tmp_path)
    log.record(date(2024, 2, 6), "1d", "complete")

    windows = build_update_windows(log, ["1d"], None, date(2024, 2, 6))

    assert windows == []


def test_build_update_windows_handles_different_freq_latest_dates(
    tmp_path: Path,
) -> None:
    log = IngestionLog(tmp_path)
    log.record(date(2024, 2, 2), "1d", "complete")
    log.record(date(2024, 2, 5), "1min", "complete")

    windows = build_update_windows(log, ["1d", "1min"], None, date(2024, 2, 6))

    assert [(window.freq, window.start) for window in windows] == [
        ("1d", date(2024, 2, 5)),
        ("1min", date(2024, 2, 6)),
    ]


def test_default_update_end_uses_previous_trading_day() -> None:
    assert default_update_end(date(2024, 2, 5)) == date(2024, 2, 2)
