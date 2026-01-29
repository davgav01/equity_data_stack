"""Security master utilities."""

from pathlib import Path

import pandas as pd

SECURITY_MASTER_COLUMNS = [
    "symbol",
    "name",
    "exchange",
    "type",
    "sector",
    "industry",
    "is_active",
]


def load_security_master(data_root: Path) -> pd.DataFrame:
    path = Path(data_root) / "security_master.parquet"
    if not path.exists():
        return pd.DataFrame(columns=SECURITY_MASTER_COLUMNS)
    return pd.read_parquet(path)
