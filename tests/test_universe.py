from datetime import date, datetime
from pathlib import Path

import pandas as pd

from equity_data_stack.ingest import backfill_bars
from equity_data_stack.ingestion_log import IngestionLog
from equity_data_stack.providers.base import ProviderInterface
from equity_data_stack.storage import StorageManager
from equity_data_stack.universe import (
    build_universe_snapshot,
    get_universe,
    load_universe_snapshot,
)


class DummyProvider(ProviderInterface):
    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df

    def get_bars(self, symbol_universe, trading_day, freq):
        return self._df

    def get_securities(self) -> pd.DataFrame:
        return pd.DataFrame()

    def get_splits(
        self, start: date | None = None, end: date | None = None
    ) -> pd.DataFrame:
        return pd.DataFrame()

    def get_dividends(
        self, start: date | None = None, end: date | None = None
    ) -> pd.DataFrame:
        return pd.DataFrame()


def _sample_bars() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": [
                datetime(2024, 1, 2, 14, 30),
                datetime(2024, 1, 2, 20, 0),
                datetime(2024, 1, 2, 20, 0),
            ],
            "symbol": ["AAA", "AAA", "BBB"],
            "open": [10.0, 10.5, 20.0],
            "high": [10.5, 10.6, 20.5],
            "low": [9.8, 10.2, 19.8],
            "close": [10.2, 10.4, 21.0],
            "vwap": [10.1, 10.45, 20.8],
            "volume": [100, 150, 200],
            "n_trades": [5, 6, 7],
        }
    )


def test_build_universe_snapshot_computes_notional() -> None:
    bars = _sample_bars()
    snapshot = build_universe_snapshot(date(2024, 1, 2), bars, pd.DataFrame())

    aaa = snapshot[snapshot["symbol"] == "AAA"].iloc[0]
    bbb = snapshot[snapshot["symbol"] == "BBB"].iloc[0]

    assert aaa["notional"] == 10.4 * (100 + 150)
    assert bbb["notional"] == 21.0 * 200


def test_storage_and_query_universe_snapshot(tmp_path: Path) -> None:
    bars = _sample_bars()
    storage = StorageManager(tmp_path)
    snapshot = build_universe_snapshot(date(2024, 1, 2), bars, pd.DataFrame())
    storage.write_universe_snapshot(snapshot, date(2024, 1, 2))

    loaded = load_universe_snapshot(tmp_path, date(2024, 1, 2))
    assert not loaded.empty
    symbols = get_universe(tmp_path, date(2024, 1, 2), top_n=1)
    assert symbols == ["BBB"]


def test_backfill_writes_universe_snapshot(tmp_path: Path) -> None:
    bars = _sample_bars()
    provider = DummyProvider(bars)

    storage = StorageManager(tmp_path)
    log = IngestionLog(tmp_path)

    backfill_bars(
        provider=provider,
        storage=storage,
        log=log,
        start=date(2024, 1, 2),
        end=date(2024, 1, 2),
        freq="1d",
        write_universe_snapshots=True,
        security_master=pd.DataFrame(),
    )

    snapshot_path = tmp_path / "universe" / "snapshots" / "date=2024-01-02.parquet"
    assert snapshot_path.exists()
