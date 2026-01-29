"""Query layer using DuckDB."""

from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

from equity_data_stack.settings import Settings


def load_prices(
    freq: str,
    symbols: list[str],
    start: datetime,
    end: datetime,
    fields: list[str] | None = None,
    data_root: Path | None = None,
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

    return wide.sort_index()


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
