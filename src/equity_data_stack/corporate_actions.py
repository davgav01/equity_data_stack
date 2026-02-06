"""Corporate actions utilities for split/dividend tables and adjustments."""

from datetime import date, datetime
from pathlib import Path

import pandas as pd

from equity_data_stack.query import load_prices

SPLIT_RATIO_FILENAME = "split_ratios.parquet"
DIVIDEND_CASH_FILENAME = "cash_dividends.parquet"


def build_corporate_actions_tables(
    data_root: Path,
    start: date | None = None,
    end: date | None = None,
) -> tuple[Path, Path]:
    """Build split ratio and dividend cash tables under corporate_actions/."""
    split_path = build_split_ratio_table(data_root, start=start, end=end)
    dividend_path = build_dividend_cash_table(data_root, start=start, end=end)
    return split_path, dividend_path


def build_split_ratio_table(
    data_root: Path,
    start: date | None = None,
    end: date | None = None,
) -> Path:
    """Build split ratio wide table (date x symbol) for backward adjustment."""
    root = Path(data_root)
    splits_path = root / "corporate_actions" / "splits.parquet"
    splits = pd.read_parquet(splits_path) if splits_path.exists() else pd.DataFrame()
    table = _build_split_ratio_table(splits, start=start, end=end)
    path = _split_ratio_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    table.to_parquet(path, index=True)
    return path


def build_dividend_cash_table(
    data_root: Path,
    start: date | None = None,
    end: date | None = None,
) -> Path:
    """Build dividend cash wide table (date x symbol)."""
    root = Path(data_root)
    dividends_path = root / "corporate_actions" / "dividends.parquet"
    dividends = (
        pd.read_parquet(dividends_path) if dividends_path.exists() else pd.DataFrame()
    )
    table = _build_dividend_cash_table(dividends, start=start, end=end)
    path = _dividend_cash_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    table.to_parquet(path, index=True)
    return path


def load_split_ratio_table(
    data_root: Path,
    start: date | None = None,
    end: date | None = None,
    symbols: list[str] | None = None,
) -> pd.DataFrame:
    """Load split ratio wide table with optional filters."""
    path = _split_ratio_path(Path(data_root))
    if not path.exists():
        return pd.DataFrame()
    table = pd.read_parquet(path)
    table.index = pd.to_datetime(table.index).date
    return _filter_table(table, start=start, end=end, symbols=symbols)


def load_dividend_cash_table(
    data_root: Path,
    start: date | None = None,
    end: date | None = None,
    symbols: list[str] | None = None,
) -> pd.DataFrame:
    """Load dividend cash wide table with optional filters."""
    path = _dividend_cash_path(Path(data_root))
    if not path.exists():
        return pd.DataFrame()
    table = pd.read_parquet(path)
    table.index = pd.to_datetime(table.index).date
    return _filter_table(table, start=start, end=end, symbols=symbols)


def compute_split_factors(
    prices: pd.DataFrame, split_ratios: pd.DataFrame
) -> pd.DataFrame:
    """Compute backward split adjustment factors aligned to prices index."""
    prices = _ensure_price_frame(prices)
    if split_ratios.empty:
        return pd.DataFrame(1.0, index=prices.index, columns=prices.columns)

    daily_prices = _to_daily_prices(prices)
    ratios = split_ratios.reindex(
        index=daily_prices.index, columns=daily_prices.columns
    ).fillna(1.0)

    factors_daily = _backward_factors(ratios)
    return _align_factors_to_prices(factors_daily, prices)


def compute_dividend_factors(
    prices: pd.DataFrame,
    dividend_cash: pd.DataFrame,
    price_field: str = "close",
) -> pd.DataFrame:
    """Compute backward dividend adjustment factors aligned to prices index."""
    prices = _ensure_price_frame(prices, price_field)
    if dividend_cash.empty:
        return pd.DataFrame(1.0, index=prices.index, columns=prices.columns)

    daily_prices = _to_daily_prices(prices)
    cash = dividend_cash.reindex(
        index=daily_prices.index, columns=daily_prices.columns
    ).fillna(0.0)

    # Use prior trading-day close for dividend adjustment (standard convention).
    prior_close = daily_prices.shift(1)
    denom = prior_close.fillna(daily_prices)

    ratio = 1 - cash.div(denom)
    ratio = ratio.replace([float("inf"), float("-inf")], 1.0).fillna(1.0)
    factors_daily = _backward_factors(ratio)
    return _align_factors_to_prices(factors_daily, prices)


def apply_price_adjustments(
    prices: pd.DataFrame,
    split_ratios: pd.DataFrame,
    dividend_cash: pd.DataFrame,
    price_field: str = "close",
) -> pd.DataFrame:
    """Apply split and dividend adjustments to prices."""
    prices = _ensure_price_frame(prices, price_field)
    split_factors = compute_split_factors(prices, split_ratios)
    dividend_factors = compute_dividend_factors(
        prices, dividend_cash, price_field=price_field
    )
    return prices * split_factors * dividend_factors


def apply_volume_adjustments(
    volumes: pd.DataFrame,
    split_ratios: pd.DataFrame,
) -> pd.DataFrame:
    """Apply split adjustments to volumes (inverse of price split factors)."""
    volumes = _ensure_price_frame(volumes)
    split_factors = compute_split_factors(volumes, split_ratios)
    return volumes.div(split_factors)


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
    print(data_root)
    prices = load_prices(
        freq=freq,
        symbols=symbols,
        start=start,
        end=end,
        fields=[price_field],
        data_root=data_root,
    )
    print(data_root)
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


def _build_split_ratio_table(
    splits: pd.DataFrame,
    start: date | None,
    end: date | None,
) -> pd.DataFrame:
    if splits.empty:
        return pd.DataFrame()

    splits = splits.copy()
    splits["date"] = pd.to_datetime(splits["execution_date"]).dt.date
    if start is not None:
        splits = splits[splits["date"] >= start]
    if end is not None:
        splits = splits[splits["date"] <= end]

    splits["split_ratio"] = splits["split_from"] / splits["split_to"]
    split_wide = splits.pivot_table(
        index="date", columns="symbol", values="split_ratio", aggfunc="prod"
    )
    return split_wide.sort_index()


def _build_dividend_cash_table(
    dividends: pd.DataFrame,
    start: date | None,
    end: date | None,
) -> pd.DataFrame:
    if dividends.empty:
        return pd.DataFrame()

    dividends = dividends.copy()
    dividends["date"] = pd.to_datetime(dividends["ex_dividend_date"]).dt.date
    if start is not None:
        dividends = dividends[dividends["date"] >= start]
    if end is not None:
        dividends = dividends[dividends["date"] <= end]

    div_wide = dividends.pivot_table(
        index="date", columns="symbol", values="cash_amount", aggfunc="sum"
    )
    return div_wide.sort_index()


def _filter_table(
    table: pd.DataFrame,
    start: date | None,
    end: date | None,
    symbols: list[str] | None,
) -> pd.DataFrame:
    if table.empty:
        return table
    if start is not None:
        table = table[table.index >= start]
    if end is not None:
        table = table[table.index <= end]
    if symbols is not None:
        table = table.loc[:, [symbol for symbol in symbols if symbol in table.columns]]
    return table


def _split_ratio_path(data_root: Path) -> Path:
    return data_root / "corporate_actions" / SPLIT_RATIO_FILENAME


def _dividend_cash_path(data_root: Path) -> Path:
    return data_root / "corporate_actions" / DIVIDEND_CASH_FILENAME


def _to_daily_prices(prices: pd.DataFrame) -> pd.DataFrame:
    if isinstance(prices.index, pd.DatetimeIndex):
        return prices.groupby(prices.index.date).last()
    return prices


def _backward_factors(ratios: pd.DataFrame) -> pd.DataFrame:
    return (
        ratios.sort_index(ascending=False)
        .cumprod()
        .shift(1, fill_value=1.0)
        .sort_index()
    )


def _align_factors_to_prices(
    factors_daily: pd.DataFrame, prices: pd.DataFrame
) -> pd.DataFrame:
    if isinstance(prices.index, pd.DatetimeIndex):
        aligned = factors_daily.reindex(prices.index.date)
        aligned.index = prices.index
        return aligned
    return factors_daily.reindex(prices.index).fillna(1.0)


def _ensure_price_frame(
    prices: pd.DataFrame, price_field: str | None = None
) -> pd.DataFrame:
    if isinstance(prices.columns, pd.MultiIndex):
        if price_field is None:
            raise ValueError("price_field is required for multi-field price tables")
        if price_field not in prices.columns.get_level_values(0):
            raise ValueError(f"Missing field '{price_field}' in price columns")
        return prices[price_field]
    return prices
