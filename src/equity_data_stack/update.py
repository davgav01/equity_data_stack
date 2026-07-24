"""Incremental update orchestration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime

from equity_data_stack.corporate_actions import build_corporate_actions_tables
from equity_data_stack.exchange_calendar import (
    get_previous_trading_day,
    get_strictly_next_trading_day,
)
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

SUPPORTED_FREQS = ("1d", "1min")
PREFIX_BY_FREQ = {
    "1d": "us_stocks_sip/day_aggs_v1",
    "1min": "us_stocks_sip/minute_aggs_v1",
}


@dataclass(frozen=True)
class UpdateWindow:
    freq: str
    start: date
    end: date
    latest_complete: date | None = None


@dataclass(frozen=True)
class FrequencyUpdateResult:
    freq: str
    start: date | None
    end: date | None
    downloaded: int = 0
    skipped: int = 0
    missing: int = 0
    partitions: int = 0

    @property
    def did_work(self) -> bool:
        return self.start is not None and self.end is not None


@dataclass(frozen=True)
class UpdateResult:
    end: date
    frequencies: list[FrequencyUpdateResult]
    synced_reference_data: bool
    corporate_actions_start: date | None


def default_update_end(today: date | None = None) -> date:
    """Return the conservative default end date for an update run."""
    current_date = today or datetime.now(UTC).date()
    return get_previous_trading_day(current_date)


def build_update_windows(
    log: IngestionLog,
    freqs: list[str],
    fallback_start: date | None,
    end: date,
) -> list[UpdateWindow]:
    """Build per-frequency update windows from ingestion log state."""
    windows: list[UpdateWindow] = []
    for freq in freqs:
        _validate_freq(freq)
        latest = log.latest_complete_date(freq)
        if latest is None:
            if fallback_start is None:
                raise ValueError(
                    f"No completed ingestion found for freq={freq}. "
                    "Pass --start YYYY-MM-DD for the first update."
                )
            start = fallback_start
        else:
            start = get_strictly_next_trading_day(latest)

        if start <= end:
            windows.append(UpdateWindow(freq=freq, start=start, end=end))

    return windows


def run_incremental_update(
    settings: Settings,
    freqs: list[str],
    fallback_start: date | None = None,
    end: date | None = None,
    write_universe: bool = True,
    sync_reference_data: bool = True,
    event_logger: Callable[[str], None] | None = None,
) -> UpdateResult:
    """Sync raw files and ingest missing partitions through the update end date."""
    emit = event_logger or _noop_logger
    settings.ensure_data_root()
    update_end = end or default_update_end()
    emit(f"resolved data_root={settings.data_root}")
    emit(f"resolved end={update_end}")
    storage = StorageManager(settings.data_root)
    log = IngestionLog(settings.data_root)
    windows = build_update_windows(log, freqs, fallback_start, update_end)
    _emit_window_summary(emit, log, freqs, windows, update_end)

    results: list[FrequencyUpdateResult] = []
    for window in windows:
        prefix = PREFIX_BY_FREQ[window.freq]
        emit(
            f"{window.freq} raw sync start: "
            f"prefix={prefix}, start={window.start}, end={window.end}"
        )
        try:
            counts = sync_flat_files(
                settings=settings,
                start=window.start,
                end=window.end,
                prefix=prefix,
                data_root=settings.data_root,
            )
        except Exception as exc:
            emit(f"{window.freq} raw sync failed: {type(exc).__name__}: {exc}")
            raise
        emit(
            f"{window.freq} raw sync complete: "
            f"downloaded={counts['downloaded']}, "
            f"skipped={counts['skipped']}, missing={counts['missing']}"
        )

        emit(
            f"{window.freq} parquet ingest start: "
            f"start={window.start}, end={window.end}, "
            f"write_universe={write_universe and window.freq == '1d'}"
        )
        try:
            provider = MassiveProvider(settings, dataset_prefix=prefix)
            paths = backfill_bars(
                provider=provider,
                storage=storage,
                log=log,
                start=window.start,
                end=window.end,
                freq=window.freq,
                write_universe_snapshots=write_universe and window.freq == "1d",
            )
        except Exception as exc:
            emit(f"{window.freq} parquet ingest failed: {type(exc).__name__}: {exc}")
            raise
        emit(f"{window.freq} parquet ingest complete: partitions={len(paths)}")
        results.append(
            FrequencyUpdateResult(
                freq=window.freq,
                start=window.start,
                end=window.end,
                downloaded=counts["downloaded"],
                skipped=counts["skipped"],
                missing=counts["missing"],
                partitions=len(paths),
            )
        )

    for freq in freqs:
        _validate_freq(freq)
        if not any(result.freq == freq for result in results):
            results.append(FrequencyUpdateResult(freq=freq, start=None, end=None))

    corporate_actions_start = _earliest_start(windows)
    if sync_reference_data:
        provider = MassiveProvider(settings)
        emit("security master sync start")
        try:
            security_master_path = sync_security_master(provider, storage)
        except Exception as exc:
            emit(f"security master sync failed: {type(exc).__name__}: {exc}")
            raise
        emit(f"security master sync complete: path={security_master_path}")
        if corporate_actions_start is not None:
            emit(
                "corporate actions sync start: "
                f"start={corporate_actions_start}, end={update_end}"
            )
            try:
                corporate_action_paths = sync_corporate_actions(
                    provider,
                    storage,
                    start=corporate_actions_start,
                    end=update_end,
                )
            except Exception as exc:
                emit(f"corporate actions sync failed: {type(exc).__name__}: {exc}")
                raise
            emit(
                "corporate actions sync complete: "
                f"paths={','.join(corporate_action_paths)}"
            )

            emit(
                "corporate actions table build start: "
                f"start={corporate_actions_start}, end={update_end}"
            )
            try:
                split_path, dividend_path = build_corporate_actions_tables(
                    settings.data_root,
                    start=corporate_actions_start,
                    end=update_end,
                )
            except Exception as exc:
                emit(
                    "corporate actions table build failed: "
                    f"{type(exc).__name__}: {exc}"
                )
                raise
            emit(
                "corporate actions table build complete: "
                f"split_path={split_path}, dividend_path={dividend_path}"
            )
        else:
            emit("corporate actions skipped: no new bar windows")
    else:
        emit("reference data skipped")

    return UpdateResult(
        end=update_end,
        frequencies=results,
        synced_reference_data=sync_reference_data,
        corporate_actions_start=corporate_actions_start,
    )


def _earliest_start(windows: list[UpdateWindow]) -> date | None:
    if not windows:
        return None
    return min(window.start for window in windows)


def _validate_freq(freq: str) -> None:
    if freq not in SUPPORTED_FREQS:
        raise ValueError(f"Unsupported frequency: {freq}. Use 1d or 1min.")


def _emit_window_summary(
    emit: Callable[[str], None],
    log: IngestionLog,
    freqs: list[str],
    windows: list[UpdateWindow],
    update_end: date,
) -> None:
    windows_by_freq = {window.freq: window for window in windows}
    for freq in freqs:
        latest = log.latest_complete_date(freq)
        window = windows_by_freq.get(freq)
        latest_text = latest.isoformat() if latest else "none"
        if window is None:
            emit(
                f"{freq} window resolved: latest_complete={latest_text}, "
                f"status=already-current, current_through={update_end}"
            )
            continue
        emit(
            f"{freq} window resolved: latest_complete={latest_text}, "
            f"start={window.start}, end={window.end}"
        )


def _noop_logger(_: str) -> None:
    return None
