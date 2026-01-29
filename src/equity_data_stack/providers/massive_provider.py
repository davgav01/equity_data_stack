"""Massive provider: flat files for bars, REST for reference data."""

from __future__ import annotations

import gzip
import inspect
from datetime import date
from pathlib import Path

import pandas as pd

from equity_data_stack.exchange_calendar import get_trading_days
from equity_data_stack.providers.base import ProviderInterface
from equity_data_stack.settings import Settings


class MassiveProvider(ProviderInterface):
    """Use Massive flat files for bars and Massive REST for reference data."""

    def __init__(
        self,
        settings: Settings,
        dataset_prefix: str | None = None,
    ) -> None:
        self.settings = settings
        self.dataset_prefix = (
            dataset_prefix or settings.massive_s3_prefix or "us_stocks_sip/day_aggs_v1"
        )
        self._rest_client = None

    def get_bars(
        self,
        symbol_universe: list[str],
        trading_day: date,
        freq: str,
    ) -> pd.DataFrame:
        """Return daily/1-min bar data for a single trading day."""
        df = self.fetch_day(trading_day, freq)
        if symbol_universe:
            df = df[df["symbol"].isin(symbol_universe)]
        return df

    def fetch_day(self, trading_day: date, freq: str) -> pd.DataFrame:
        """Load a single trading day flat file and normalize columns."""
        path = self._bar_path(trading_day, freq)
        if not path.exists():
            raise FileNotFoundError(f"Missing flat file: {path}")

        df = _read_flat_file(path)
        return _normalize_bars(df)

    def get_securities(self) -> pd.DataFrame:
        """Fetch and normalize the security master table via REST."""
        client = self._rest_client_or_raise()
        records = _collect(client.list_tickers, market="stocks", limit=1000)
        df = pd.DataFrame(records)
        df = df.rename(
            columns={
                "ticker": "symbol",
                "primary_exchange": "exchange",
                "active": "is_active",
            }
        )
        df = _ensure_columns(
            df,
            ["symbol", "name", "exchange", "type", "sector", "industry", "is_active"],
            ["sector", "industry"],
        )
        return df

    def get_splits(
        self, start: date | None = None, end: date | None = None
    ) -> pd.DataFrame:
        """Fetch split events, optionally server-filtered by execution_date."""
        client = self._rest_client_or_raise()
        if (start or end) and not _supports_params(client.list_splits):
            raise ValueError(
                "Massive SDK lacks params support; cannot server-filter splits"
            )
        params = _build_date_params("execution_date", start, end)
        records = _collect(
            client.list_splits,
            limit=1000,
            params=params if _supports_params(client.list_splits) else None,
        )
        df = pd.DataFrame(records)
        df = df.rename(columns={"ticker": "symbol"})
        df = _ensure_columns(
            df, ["symbol", "execution_date", "split_from", "split_to"], []
        )
        return _filter_date_range(df, "execution_date", start, end)

    def get_dividends(
        self, start: date | None = None, end: date | None = None
    ) -> pd.DataFrame:
        """Fetch dividend events, optionally server-filtered by ex_dividend_date."""
        client = self._rest_client_or_raise()
        if (start or end) and not _supports_params(client.list_dividends):
            raise ValueError(
                "Massive SDK lacks params support; cannot server-filter dividends"
            )
        params = _build_date_params("ex_dividend_date", start, end)
        records = _collect(
            client.list_dividends,
            limit=1000,
            params=params if _supports_params(client.list_dividends) else None,
        )
        df = pd.DataFrame(records)
        df = df.rename(columns={"ticker": "symbol"})
        df = _ensure_columns(df, ["symbol", "ex_dividend_date", "cash_amount"], [])
        return _filter_date_range(df, "ex_dividend_date", start, end)

    def _bar_path(self, trading_day: date, freq: str) -> Path:
        """Resolve local flat-file path for a given day/frequency."""
        date_path = trading_day.strftime("%Y/%m")
        prefix = self.dataset_prefix
        if freq == "1d":
            if "day_aggs" not in prefix:
                prefix = "us_stocks_sip/day_aggs_v1"
        elif freq == "1min":
            if "minute_aggs" not in prefix:
                prefix = "us_stocks_sip/minute_aggs_v1"
        else:
            raise ValueError(
                f"Unsupported frequency: {freq}. "
                "Use freq=1d or freq=1min for Massive flat files."
            )

        base = self.settings.data_root / "raw" / "massive" / prefix
        filename = f"{trading_day.isoformat()}.csv.gz"
        path = base / date_path / filename
        if path.exists():
            return path

        legacy_path = base / trading_day.strftime("%Y/%m/%Y-%m-%d") / filename
        return legacy_path

    def _rest_client_or_raise(self):
        if self._rest_client is not None:
            return self._rest_client

        try:
            from massive import RESTClient
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError(
                "massive SDK is required for reference data. Install with: pip install massive"
            ) from exc

        api_key = self.settings.polygon_api_key
        if api_key is None:
            raise ValueError("POLYGON_API_KEY is required for Massive REST")

        self._rest_client = RESTClient(api_key.get_secret_value())
        return self._rest_client


def _read_flat_file(path: Path) -> pd.DataFrame:
    if path.suffixes[-2:] == [".csv", ".gz"]:
        with gzip.open(path, "rt") as handle:
            return pd.read_csv(handle)
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    if path.suffix == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported flat file extension: {path.name}")


def _normalize_bars(df: pd.DataFrame) -> pd.DataFrame:
    column_map = {
        "ticker": "symbol",
        "t": "timestamp",
        "timestamp": "timestamp",
        "window_start": "timestamp",
        "T": "symbol",
        "symbol": "symbol",
        "o": "open",
        "open": "open",
        "h": "high",
        "high": "high",
        "l": "low",
        "low": "low",
        "c": "close",
        "close": "close",
        "vw": "vwap",
        "vwap": "vwap",
        "v": "volume",
        "volume": "volume",
        "n": "n_trades",
        "n_trades": "n_trades",
        "transactions": "n_trades",
    }

    df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})

    if "timestamp" not in df.columns:
        raise ValueError("Missing timestamp column after normalization")
    if "symbol" not in df.columns:
        raise ValueError("Missing symbol column after normalization")

    if pd.api.types.is_numeric_dtype(df["timestamp"]):
        df["timestamp"] = _to_datetime_utc(df["timestamp"])
    else:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    df["symbol"] = df["symbol"].astype(str)

    if "vwap" not in df.columns and "close" in df.columns:
        df["vwap"] = df["close"]
    if "n_trades" not in df.columns:
        df["n_trades"] = 0
    if "volume" not in df.columns:
        df["volume"] = 0

    return df


def _to_datetime_utc(series: pd.Series) -> pd.Series:
    max_val = series.max()
    if max_val > 1_000_000_000_000_000:  # nanoseconds
        unit = "ns"
    elif max_val > 1_000_000_000_000:  # milliseconds
        unit = "ms"
    else:
        unit = "s"
    return pd.to_datetime(series, unit=unit, utc=True)


def _collect(fn, **kwargs) -> list[dict]:
    """Collect paginated items from Massive SDK generator."""
    records: list[dict] = []
    call_kwargs = {key: value for key, value in kwargs.items() if value is not None}
    for item in fn(**call_kwargs):
        records.append(_to_dict(item))
    return records


def _to_dict(item) -> dict:
    if isinstance(item, dict):
        return item
    if hasattr(item, "model_dump"):
        return item.model_dump()
    if hasattr(item, "to_dict"):
        return item.to_dict()
    return vars(item)


def _ensure_columns(
    df: pd.DataFrame, required: list[str], optional: list[str]
) -> pd.DataFrame:
    for col in optional:
        if col not in df.columns:
            df[col] = pd.NA
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in reference table: {missing}")
    return df


def _supports_params(fn) -> bool:
    signature = inspect.signature(fn)
    if "params" in signature.parameters:
        return True
    return any(
        param.kind == inspect.Parameter.VAR_KEYWORD
        for param in signature.parameters.values()
    )


def _build_date_params(
    field: str, start: date | None, end: date | None
) -> dict[str, str]:
    params: dict[str, str] = {}
    if start is not None:
        params[f"{field}.gte"] = start.isoformat()
    if end is not None:
        params[f"{field}.lte"] = end.isoformat()
    return params


def _filter_date_range(
    df: pd.DataFrame,
    column: str,
    start: date | None,
    end: date | None,
) -> pd.DataFrame:
    if (start is None and end is None) or column not in df.columns:
        return df

    dates = pd.to_datetime(df[column], errors="coerce").dt.date
    mask = pd.Series(True, index=df.index)
    if start is not None:
        mask &= dates >= start
    if end is not None:
        mask &= dates <= end
    return df.loc[mask]
