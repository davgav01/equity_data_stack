"""Command line interface for equity_data_stack."""

from datetime import UTC, date, datetime
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
from equity_data_stack.update import SUPPORTED_FREQS, run_incremental_update

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
UPDATE_WRITE_UNIVERSE_OPTION = typer.Option(
    True,
    "--write-universe/--no-write-universe",
    help="Write daily universe snapshots during update",
)
UPDATE_FREQ_OPTION = typer.Option(
    None,
    "--freq",
    help="Frequency to update. Repeat for multiple values. Defaults to 1d and 1min.",
)
SKIP_REFERENCE_DATA_OPTION = typer.Option(
    False, help="Skip security master, corporate actions sync, and action table rebuild"
)
LOG_LIMIT_OPTION = typer.Option(50, help="Number of ingestion log rows to print")


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


@app.command(name="update")
def update_cmd(
    start: str | None = OPTIONAL_START_OPTION,
    end: str | None = OPTIONAL_END_OPTION,
    freq: list[str] | None = UPDATE_FREQ_OPTION,
    data_root: Path | None = DATA_ROOT_OPTION,
    write_universe: bool = UPDATE_WRITE_UNIVERSE_OPTION,
    skip_reference_data: bool = SKIP_REFERENCE_DATA_OPTION,
) -> None:
    settings = Settings()
    if data_root:
        settings.data_root = data_root

    freqs = freq or list(SUPPORTED_FREQS)
    start_date = date.fromisoformat(start) if start else None
    end_date = date.fromisoformat(end) if end else None

    run_started_at = datetime.now(UTC)
    _echo_update_event(
        "update run start: "
        f"freqs={','.join(freqs)}, "
        f"requested_start={start_date.isoformat() if start_date else 'from-log'}, "
        f"requested_end={end_date.isoformat() if end_date else 'previous-trading-day'}"
    )
    try:
        result = run_incremental_update(
            settings=settings,
            freqs=freqs,
            fallback_start=start_date,
            end=end_date,
            write_universe=write_universe,
            sync_reference_data=not skip_reference_data,
            event_logger=_echo_update_event,
        )
    except ValueError as exc:
        _echo_update_event(f"update run failed: {type(exc).__name__}: {exc}")
        raise typer.BadParameter(str(exc)) from exc
    except Exception as exc:
        _echo_update_event(f"update run failed: {type(exc).__name__}: {exc}")
        raise

    for freq_result in result.frequencies:
        if not freq_result.did_work:
            _echo_update_event(
                f"{freq_result.freq} summary: already current through {result.end}"
            )
            continue
        _echo_update_event(
            f"{freq_result.freq} summary: start={freq_result.start}, "
            f"end={freq_result.end}, "
            f"downloaded={freq_result.downloaded}, "
            f"skipped={freq_result.skipped}, "
            f"missing={freq_result.missing}, "
            f"partitions={freq_result.partitions}"
        )

    if result.synced_reference_data:
        if result.corporate_actions_start is None:
            _echo_update_event(
                "reference data summary: synced=true, "
                "corporate_actions=skipped-no-new-bars"
            )
        else:
            _echo_update_event(
                "reference data summary: synced=true, "
                f"corporate_actions_start={result.corporate_actions_start}, "
                f"corporate_actions_end={result.end}"
            )
    else:
        _echo_update_event("reference data summary: synced=false")

    duration_seconds = (datetime.now(UTC) - run_started_at).total_seconds()
    _echo_update_event(f"update run complete: duration_seconds={duration_seconds:.2f}")


@app.command(name="log-tail")
def log_tail_cmd(
    limit: int = LOG_LIMIT_OPTION,
    data_root: Path | None = DATA_ROOT_OPTION,
) -> None:
    settings = Settings()
    if data_root:
        settings.data_root = data_root
    log = IngestionLog(settings.data_root)
    df = log.tail(limit)
    if df.empty:
        typer.echo("No ingestion log entries")
        return
    typer.echo(df.to_string(index=False))


def _echo_update_event(message: str) -> None:
    timestamp = datetime.now(UTC).isoformat(timespec="seconds")
    typer.echo(f"{timestamp} {message}")


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
