"""S3 flat-file sync utilities for Massive datasets."""

from datetime import date
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from equity_data_stack.exchange_calendar import get_trading_days
from equity_data_stack.settings import Settings


def sync_flat_files(
    settings: Settings,
    start: date,
    end: date,
    prefix: str | None = None,
    data_root: Path | None = None,
    ext: str = "csv.gz",
) -> dict[str, int]:
    """Sync Massive flat files from S3 to local disk.

    Returns counts for downloaded, skipped, and missing files.
    """
    if not settings.massive_access_key or not settings.massive_secret_key:
        raise ValueError("MASSIVE_ACCESS_KEY and MASSIVE_SECRET_KEY are required")
    access_key = settings.massive_access_key.get_secret_value()
    secret_key = settings.massive_secret_key.get_secret_value()

    endpoint = settings.massive_s3_endpoint
    bucket = settings.massive_s3_bucket
    if not endpoint or not bucket:
        raise ValueError("MASSIVE_S3_ENDPOINT and MASSIVE_S3_BUCKET are required")

    dataset_prefix = prefix or settings.massive_s3_prefix
    if not dataset_prefix:
        raise ValueError("MASSIVE_S3_PREFIX is required")

    root = Path(data_root) if data_root else settings.data_root

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )

    days = get_trading_days(start, end)

    counts = {"downloaded": 0, "skipped": 0, "missing": 0}
    for day in days:
        key = _build_key(dataset_prefix, day, ext)
        local_path = _local_path(root, dataset_prefix, day, ext)

        if local_path.exists():
            counts["skipped"] += 1
            continue

        local_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            client.download_file(bucket, key, str(local_path))
            counts["downloaded"] += 1
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey"}:
                counts["missing"] += 1
                continue
            if code in {"403", "AccessDenied"}:
                raise ValueError(
                    "S3 access denied. Check MASSIVE_ACCESS_KEY/SECRET, "
                    "bucket, and subscription permissions for the prefix."
                ) from exc
            raise

    return counts


def _build_key(prefix: str, trading_day: date, ext: str) -> str:
    date_path = trading_day.strftime("%Y/%m")
    filename = f"{trading_day.isoformat()}.{ext}"
    return f"{prefix}/{date_path}/{filename}"


def _local_path(root: Path, prefix: str, trading_day: date, ext: str) -> Path:
    date_path = trading_day.strftime("%Y/%m")
    filename = f"{trading_day.isoformat()}.{ext}"
    return root / "raw" / "massive" / prefix / date_path / filename
