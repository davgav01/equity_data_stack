from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from equity_data_stack.query import load_prices
from equity_data_stack.storage import StorageManager


def test_load_prices_returns_wide_frame(tmp_path: Path) -> None:
    storage = StorageManager(tmp_path)
    df = pd.DataFrame(
        [
            {
                "timestamp": datetime(2024, 1, 2, 16, 0),
                "symbol": "AAPL",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "vwap": 100.2,
                "volume": 1000,
                "n_trades": 10,
            },
            {
                "timestamp": datetime(2024, 1, 2, 16, 0),
                "symbol": "MSFT",
                "open": 200.0,
                "high": 202.0,
                "low": 198.0,
                "close": 201.5,
                "vwap": 201.0,
                "volume": 2000,
                "n_trades": 20,
            },
        ]
    )
    storage.write_bars(df, "1d")

    result = load_prices(
        freq="1d",
        symbols=["AAPL", "MSFT"],
        start=datetime(2024, 1, 2),
        end=datetime(2024, 1, 2, 23, 59),
        fields=["close"],
        data_root=tmp_path,
    )

    assert list(result.columns) == ["AAPL", "MSFT"]
    assert result.loc[pd.Timestamp("2024-01-02 16:00:00+00:00"), "AAPL"] == 100.5


def test_load_prices_rejects_empty_symbols(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="symbols must be a non-empty list"):
        load_prices(
            freq="1d",
            symbols=[],
            start=datetime(2024, 1, 2),
            end=datetime(2024, 1, 2),
            data_root=tmp_path,
        )


def test_load_prices_rejects_invalid_fields(tmp_path: Path) -> None:
    storage = StorageManager(tmp_path)
    df = pd.DataFrame(
        [
            {
                "timestamp": datetime(2024, 1, 2, 16, 0),
                "symbol": "AAPL",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "vwap": 100.2,
                "volume": 1000,
                "n_trades": 10,
            }
        ]
    )
    storage.write_bars(df, "1d")

    with pytest.raises(ValueError, match="Unsupported field"):
        load_prices(
            freq="1d",
            symbols=["AAPL"],
            start=datetime(2024, 1, 2),
            end=datetime(2024, 1, 2, 23, 59),
            fields=["bad"],
            data_root=tmp_path,
        )
