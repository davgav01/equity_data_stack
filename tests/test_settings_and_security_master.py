from pathlib import Path

import pandas as pd

from equity_data_stack.security_master import SECURITY_MASTER_COLUMNS, load_security_master
from equity_data_stack.settings import Settings


def test_settings_ensure_data_root(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "data_root"
    monkeypatch.setenv("DATA_ROOT", str(data_root))

    settings = Settings()
    settings.ensure_data_root()

    assert data_root.exists()


def test_load_security_master_missing(tmp_path: Path) -> None:
    df = load_security_master(tmp_path)

    assert list(df.columns) == SECURITY_MASTER_COLUMNS
    assert df.empty


def test_load_security_master_reads_file(tmp_path: Path) -> None:
    data = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "exchange": "XNYS",
                "type": "CS",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "is_active": True,
            }
        ]
    )
    path = tmp_path / "security_master.parquet"
    data.to_parquet(path, index=False)

    loaded = load_security_master(tmp_path)

    assert loaded.shape == data.shape
    assert loaded.iloc[0]["symbol"] == "AAPL"
