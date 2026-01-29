from datetime import date
from pathlib import Path

from equity_data_stack.s3_sync import _build_key, _local_path


def test_build_key() -> None:
    key = _build_key("prefix", date(2024, 1, 2), "csv.gz")
    assert key == "prefix/2024/01/2024-01-02.csv.gz"


def test_local_path(tmp_path: Path) -> None:
    path = _local_path(tmp_path, "prefix", date(2024, 1, 2), "csv.gz")
    expected = tmp_path / "raw" / "massive" / "prefix" / "2024" / "01" / "2024-01-02.csv.gz"
    assert path == expected

