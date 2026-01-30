from datetime import date, datetime
from pathlib import Path

import pandas as pd

from equity_data_stack.ingest import backfill_bars
from equity_data_stack.ingestion_log import IngestionLog
from equity_data_stack.providers.base import ProviderInterface
from equity_data_stack.storage import StorageManager


class _StubProvider(ProviderInterface):
    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df

    def get_bars(
        self,
        symbol_universe: list[str],
        trading_day: date,
        freq: str,
    ) -> pd.DataFrame:
        if symbol_universe:
            return self._df[self._df["symbol"].isin(symbol_universe)]
        return self._df

    def get_securities(self) -> pd.DataFrame:
        return pd.DataFrame()

    def get_splits(self, start: date | None = None, end: date | None = None) -> pd.DataFrame:
        return pd.DataFrame()

    def get_dividends(self, start: date | None = None, end: date | None = None) -> pd.DataFrame:
        return pd.DataFrame()



def _bars_df() -> pd.DataFrame:
    return pd.DataFrame(
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


def test_backfill_bars_writes_and_logs(tmp_path: Path) -> None:
    provider = _StubProvider(_bars_df())
    storage = StorageManager(tmp_path)
    log = IngestionLog(tmp_path)
    trading_day = date(2024, 1, 2)

    written = backfill_bars(
        provider=provider,
        storage=storage,
        log=log,
        start=trading_day,
        end=trading_day,
        freq="1d",
    )

    assert len(written) == 1
    assert log.is_complete(trading_day, "1d")
