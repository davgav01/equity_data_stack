"""Universe snapshot utilities."""

from datetime import date
from pathlib import Path

import pandas as pd

UNIVERSE_COLUMNS = ["date", "symbol", "notional", "rank"]


def build_universe_snapshot(
    trading_day: date,
    bars_df: pd.DataFrame,
    security_master: pd.DataFrame,
) -> pd.DataFrame:
    """Build a daily universe snapshot with notional traded."""
    if bars_df.empty:
        return pd.DataFrame(columns=UNIVERSE_COLUMNS)

    bars = bars_df.copy()
    bars["timestamp"] = pd.to_datetime(bars["timestamp"], utc=True)

    if "volume" not in bars.columns:
        bars["volume"] = 0

    volume_sum = bars.groupby("symbol", as_index=False)["volume"].sum()
    last_rows = _last_row_per_symbol(bars)
    snapshot = last_rows[["symbol", "close"]].merge(volume_sum, on="symbol", how="left")
    snapshot["notional"] = snapshot["close"] * snapshot["volume"]

    snapshot["date"] = trading_day
    snapshot = snapshot[["date", "symbol", "notional"]]

    snapshot = snapshot.sort_values("notional", ascending=False)
    snapshot["rank"] = (
        snapshot["notional"]
        .rank(method="first", ascending=False)
        .where(snapshot["notional"].notna())
    )

    return snapshot.reset_index(drop=True)


def load_universe_snapshot(data_root: Path, trading_day: date) -> pd.DataFrame:
    path = _snapshot_path(Path(data_root), trading_day)
    if not path.exists():
        return pd.DataFrame(columns=UNIVERSE_COLUMNS)
    return pd.read_parquet(path)


def get_universe(
    data_root: Path, trading_day: date, top_n: int | None = None
) -> list[str]:
    snapshot = load_universe_snapshot(data_root, trading_day)
    if snapshot.empty:
        return []

    if top_n is not None:
        snapshot = snapshot.sort_values("notional", ascending=False).head(top_n)
    return snapshot["symbol"].tolist()


def _snapshot_path(data_root: Path, trading_day: date) -> Path:
    return (
        data_root / "universe" / "snapshots" / f"date={trading_day.isoformat()}.parquet"
    )


def _last_row_per_symbol(bars: pd.DataFrame) -> pd.DataFrame:
    """Return last row per symbol for a trading day."""
    bars = bars.sort_values(["symbol", "timestamp"])
    return bars.groupby("symbol", as_index=False).tail(1)
