"""Command line interface for equity_data_stack."""

from datetime import date
from pathlib import Path

import typer

from equity_data_stack.corporate_actions import build_corporate_actions_tables
from equity_data_stack.ingest import (
    backfill_bars,
    sync_corporate_actions,
    sync_security_master,
)
from equity_data_stack.ingestion_log import IngestionLog
from equity_data_stack.providers.massive_provider import MassiveProvider
from equity_data_stack.s3_sync import sync_flat_files
from equity_data_stack.settings import Settings
from equity_data_stack.storage import StorageManager

app = typer.Typer(add_completion=False, no_args_is_help=True)

DATA_ROOT_OPTION = typer.Option(None, help="Override DATA_ROOT")
START_OPTION = typer.Option(..., help="Start date YYYY-MM-DD")
END_OPTION = typer.Option(..., help="End date YYYY-MM-DD")
OPTIONAL_START_OPTION = typer.Option(None, help="Start date YYYY-MM-DD")
OPTIONAL_END_OPTION = typer.Option(None, help="End date YYYY-MM-DD")
PREFIX_OPTION = typer.Option(
    None, help="Dataset prefix (default from MASSIVE_S3_PREFIX)"
)
EXT_OPTION = typer.Option("csv.gz", help="File extension (default csv.gz)")
FREQ_OPTION = typer.Option("1d", help="Frequency: 1d or 1min")
WRITE_UNIVERSE_OPTION = typer.Option(
    False, help="Write daily universe snapshots with notional"
)


@app.command()
def sync(
    freq: str = FREQ_OPTION,
    start: str = START_OPTION,
    end: str = END_OPTION,
    data_root: Path | None = DATA_ROOT_OPTION,
    write_universe: bool = WRITE_UNIVERSE_OPTION,
) -> None:
    settings = Settings()
    if data_root:
        settings.data_root = data_root
    settings.ensure_data_root()

    typer.echo(f"Sync start: freq={freq}, start={start}, end={end}")
    provider = MassiveProvider(settings)
    storage = StorageManager(settings.data_root)
    log = IngestionLog(settings.data_root)

    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)

    paths = backfill_bars(
        provider=provider,
        storage=storage,
        log=log,
        start=start_date,
        end=end_date,
        freq=freq,
        write_universe_snapshots=write_universe,
    )
    typer.echo(f"Sync complete. Wrote {len(paths)} partitions")


@app.command(name="sync-security-master")
def sync_security_master_cmd(
    data_root: Path | None = DATA_ROOT_OPTION,
) -> None:
    settings = Settings()
    if data_root:
        settings.data_root = data_root
    settings.ensure_data_root()

    typer.echo("Sync security master start")
    provider = MassiveProvider(settings)
    storage = StorageManager(settings.data_root)

    path = sync_security_master(provider, storage)
    typer.echo(f"Sync security master complete. Wrote {path}")


@app.command(name="sync-corporate-actions")
def sync_corporate_actions_cmd(
    data_root: Path | None = DATA_ROOT_OPTION,
    start: str | None = OPTIONAL_START_OPTION,
    end: str | None = OPTIONAL_END_OPTION,
) -> None:
    settings = Settings()
    if data_root:
        settings.data_root = data_root
    settings.ensure_data_root()

    typer.echo("Sync corporate actions start")
    provider = MassiveProvider(settings)
    storage = StorageManager(settings.data_root)

    start_date = date.fromisoformat(start) if start else None
    end_date = date.fromisoformat(end) if end else None
    paths = sync_corporate_actions(provider, storage, start=start_date, end=end_date)
    typer.echo("Sync corporate actions complete. Wrote " + ", ".join(paths))


@app.command(name="build-corporate-actions-tables")
def build_corporate_actions_tables_cmd(
    data_root: Path | None = DATA_ROOT_OPTION,
    start: str | None = OPTIONAL_START_OPTION,
    end: str | None = OPTIONAL_END_OPTION,
) -> None:
    settings = Settings()
    if data_root:
        settings.data_root = data_root
    settings.ensure_data_root()

    typer.echo("Build corporate actions table start")
    start_date = date.fromisoformat(start) if start else None
    end_date = date.fromisoformat(end) if end else None
    split_path, dividend_path = build_corporate_actions_tables(
        settings.data_root,
        start=start_date,
        end=end_date,
    )
    typer.echo(
        "Build corporate actions table complete. Wrote "
        f"{split_path}, {dividend_path}"
    )


@app.command(name="sync-flat-files")
def sync_flat_files_cmd(
    start: str = START_OPTION,
    end: str = END_OPTION,
    prefix: str | None = PREFIX_OPTION,
    data_root: Path | None = DATA_ROOT_OPTION,
    ext: str = EXT_OPTION,
) -> None:
    settings = Settings()
    if data_root:
        settings.data_root = data_root
    settings.ensure_data_root()

    typer.echo(f"Sync flat files start: prefix={prefix or settings.massive_s3_prefix}")
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)

    counts = sync_flat_files(
        settings=settings,
        start=start_date,
        end=end_date,
        prefix=prefix,
        data_root=settings.data_root,
        ext=ext,
    )

    typer.echo(
        "Sync flat files complete. "
        + "Downloaded: {downloaded}, skipped: {skipped}, missing: {missing}".format(
            **counts
        )
    )


if __name__ == "__main__":
    app()
