"""Ingestion orchestration for bulk backfills."""

from datetime import date

import pandas as pd

from equity_data_stack.exchange_calendar import get_trading_days
from equity_data_stack.ingestion_log import IngestionLog
from equity_data_stack.providers.base import ProviderInterface
from equity_data_stack.security_master import load_security_master
from equity_data_stack.storage import StorageManager
from equity_data_stack.universe import build_universe_snapshot


def backfill_bars(
    provider: ProviderInterface,
    storage: StorageManager,
    log: IngestionLog,
    start: date,
    end: date,
    freq: str,
    symbol_universe: list[str] | None = None,
    write_universe_snapshots: bool = False,
    security_master: pd.DataFrame | None = None,
) -> list[str]:
    """Backfill bar data using the provider and storage manager."""
    symbol_universe = symbol_universe or []
    trading_days = get_trading_days(start, end)
    missing_days = log.missing_dates(trading_days, freq)

    written: list[str] = []
    for day in missing_days:
        log.record(day, freq, "started")
        try:
            df = provider.get_bars(symbol_universe, day, freq)
            paths = storage.write_bars(df, freq)
            written.extend([str(path) for path in paths])
            if write_universe_snapshots:
                snapshot = build_universe_snapshot(
                    day,
                    df,
                    (
                        security_master
                        if security_master is not None
                        else load_security_master(storage.data_root)
                    ),
                )
                storage.write_universe_snapshot(snapshot, day)
            log.record(day, freq, "complete")
        except Exception:
            log.record(day, freq, "failed")
            raise

    return written


def sync_security_master(provider: ProviderInterface, storage: StorageManager) -> str:
    df = provider.get_securities()
    path = storage.write_security_master(df)
    return str(path)


def sync_corporate_actions(
    provider: ProviderInterface,
    storage: StorageManager,
    start: date | None = None,
    end: date | None = None,
) -> list[str]:
    splits = provider.get_splits(start=start, end=end)
    dividends = provider.get_dividends(start=start, end=end)
    paths = [storage.write_splits(splits), storage.write_dividends(dividends)]
    return [str(path) for path in paths]
