from datetime import datetime
from pathlib import Path

import pandas as pd

from equity_data_stack.storage import StorageManager


def _bars_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "timestamp": datetime(2024, 1, 2, 9, 30),
                "symbol": "AAPL",
                "open": 100.0,
                "high": 101.0,
                "low": 99.5,
                "close": 100.5,
                "vwap": 100.2,
                "volume": 1000,
                "n_trades": 10,
            },
            {
                "timestamp": datetime(2024, 1, 2, 9, 31),
                "symbol": "AAPL",
                "open": 100.5,
                "high": 101.2,
                "low": 100.1,
                "close": 100.9,
                "vwap": 100.7,
                "volume": 1200,
                "n_trades": 12,
            },
        ]
    )


def test_write_bars_1min_partition(tmp_path: Path) -> None:
    storage = StorageManager(tmp_path)

    storage.write_bars(_bars_df(), "1min")

    expected = (
        tmp_path
        / "bars"
        / "freq=1min"
        / "year=2024"
        / "month=01"
        / "day=2024-01-02.parquet"
    )
    assert expected.exists()


def test_write_splits_dedupes_on_symbol_and_execution_date(tmp_path: Path) -> None:
    storage = StorageManager(tmp_path)

    df = pd.DataFrame(
        [
            {"symbol": "AAPL", "execution_date": "2024-01-02", "split_from": 2, "split_to": 1},
            {"symbol": "AAPL", "execution_date": "2024-01-02", "split_from": 2, "split_to": 1},
        ]
    )
    path = storage.write_splits(df)

    stored = pd.read_parquet(path)
    assert len(stored) == 1


def test_write_dividends_dedupes_on_symbol_and_ex_date(tmp_path: Path) -> None:
    storage = StorageManager(tmp_path)

    df = pd.DataFrame(
        [
            {"symbol": "AAPL", "ex_dividend_date": "2024-01-02", "cash_amount": 0.24},
            {"symbol": "AAPL", "ex_dividend_date": "2024-01-02", "cash_amount": 0.24},
        ]
    )
    path = storage.write_dividends(df)

    stored = pd.read_parquet(path)
    assert len(stored) == 1
