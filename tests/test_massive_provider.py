import gzip
from datetime import date
from pathlib import Path

import pandas as pd

from equity_data_stack.providers.massive_provider import MassiveProvider
from equity_data_stack.settings import Settings


def _write_csv_gz(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt") as handle:
        df.to_csv(handle, index=False)


def test_massive_provider_reads_daily(tmp_path: Path) -> None:
    settings = Settings(data_root=tmp_path)
    provider = MassiveProvider(settings)

    day = date(2024, 1, 2)
    base = tmp_path / "raw" / "massive" / "us_stocks_sip" / "day_aggs_v1"
    path = base / "2024/01" / "2024-01-02.csv.gz"

    df = pd.DataFrame(
        {
            "ticker": ["AAA"],
            "window_start": [1704201600000000000],
            "open": [10.0],
            "high": [10.5],
            "low": [9.8],
            "close": [10.2],
            "volume": [100],
            "transactions": [5],
        }
    )
    _write_csv_gz(path, df)

    out = provider.fetch_day(day, "1d")
    assert not out.empty
    assert "timestamp" in out.columns
    assert "symbol" in out.columns
