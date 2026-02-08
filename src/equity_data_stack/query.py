"""Query layer using DuckDB."""

from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

from equity_data_stack.corporate_actions import (
    apply_price_adjustments,
    apply_volume_adjustments,
    load_dividend_cash_table,
    load_split_ratio_table,
)
from equity_data_stack.exchange_calendar import get_trading_minutes
from equity_data_stack.settings import Settings


def load_prices(
    freq: str,
    symbols: list[str],
    start: datetime,
    end: datetime,
    fields: list[str] | None = None,
    data_root: Path | None = None,
    fill_missing_bars: bool = True,
) -> pd.DataFrame:
    """Load price data into a wide DataFrame.

    If fields has multiple entries, the resulting columns are a MultiIndex
    with (field, symbol).
    """
    if not symbols:
        raise ValueError("symbols must be a non-empty list")

    fields = fields or ["close"]
    data_root = Path(data_root) if data_root else Settings().data_root

    start_ts = _ensure_utc(start)
    end_ts = _ensure_utc(end)

    glob_path = (data_root / "bars" / f"freq={freq}" / "**" / "*.parquet").as_posix()

    placeholders = ", ".join(["?"] * len(symbols))
    field_sql = ", ".join([_sanitize_identifier(field) for field in fields])
    sql = (
        f"SELECT timestamp, symbol, {field_sql} "
        f"FROM read_parquet('{glob_path}') "
        f"WHERE symbol IN ({placeholders}) "
        "AND timestamp >= ? AND timestamp <= ?"
    )

    conn = duckdb.connect()
    params = [*symbols, start_ts, end_ts]
    df = conn.execute(sql, params).df()

    if df.empty:
        return df

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    if len(fields) == 1:
        wide = df.pivot(index="timestamp", columns="symbol", values=fields[0])
    else:
        wide = df.pivot_table(index="timestamp", columns="symbol", values=fields)

    wide = wide.sort_index()

    if freq == "1min":
        minutes = get_trading_minutes(start, end)
        wide = wide.reindex(minutes)

    if fill_missing_bars:
        wide = wide.ffill()
        wide = wide.bfill()

    return wide


def load_adjusted_prices(
    *,
    data_root: Path,
    freq: str,
    symbols: list[str],
    start: datetime,
    end: datetime,
    price_field: str = "close",
) -> pd.DataFrame:
    """Load prices and apply split/dividend adjustments."""
    prices = load_prices(
        freq=freq,
        symbols=symbols,
        start=start,
        end=end,
        fields=[price_field],
        data_root=data_root,
    )
    split_ratios = load_split_ratio_table(
        data_root,
        start=start.date(),
        end=end.date(),
        symbols=symbols,
    )
    dividend_cash = load_dividend_cash_table(
        data_root,
        start=start.date(),
        end=end.date(),
        symbols=symbols,
    )
    return apply_price_adjustments(
        prices, split_ratios, dividend_cash, price_field=price_field
    )


def load_adjusted_volumes(
    *,
    data_root: Path,
    freq: str,
    symbols: list[str],
    start: datetime,
    end: datetime,
    volume_field: str = "volume",
) -> pd.DataFrame:
    """Load volumes and apply split adjustments."""
    volumes = load_prices(
        freq=freq,
        symbols=symbols,
        start=start,
        end=end,
        fields=[volume_field],
        data_root=data_root,
    )
    split_ratios = load_split_ratio_table(
        data_root,
        start=start.date(),
        end=end.date(),
        symbols=symbols,
    )
    return apply_volume_adjustments(volumes, split_ratios)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _sanitize_identifier(value: str) -> str:
    """Basic identifier sanitation for known field names."""
    allowed = {
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
    if value not in allowed:
        raise ValueError(f"Unsupported field: {value}")
    return value
