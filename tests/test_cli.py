from datetime import date
from pathlib import Path

from typer.testing import CliRunner

from equity_data_stack.cli import app
from equity_data_stack.ingestion_log import IngestionLog
from equity_data_stack.update import FrequencyUpdateResult, UpdateResult


def test_update_cli_defaults_to_both_freqs(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    def fake_run_incremental_update(**kwargs):
        captured.update(kwargs)
        return UpdateResult(
            end=date(2024, 2, 6),
            frequencies=[
                FrequencyUpdateResult(
                    freq="1d",
                    start=date(2024, 2, 5),
                    end=date(2024, 2, 6),
                    downloaded=1,
                    skipped=0,
                    missing=0,
                    partitions=1,
                ),
                FrequencyUpdateResult(freq="1min", start=None, end=None),
            ],
            synced_reference_data=False,
            corporate_actions_start=None,
        )

    monkeypatch.setattr(
        "equity_data_stack.cli.run_incremental_update",
        fake_run_incremental_update,
    )

    result = CliRunner().invoke(
        app,
        [
            "update",
            "--start",
            "2024-02-01",
            "--end",
            "2024-02-06",
            "--data-root",
            str(tmp_path),
            "--skip-reference-data",
        ],
    )

    assert result.exit_code == 0
    assert captured["freqs"] == ["1d", "1min"]
    assert captured["fallback_start"] == date(2024, 2, 1)
    assert captured["end"] == date(2024, 2, 6)
    assert captured["sync_reference_data"] is False
    assert "requested_start=2024-02-01" in result.stdout
    assert "requested_end=2024-02-06" in result.stdout
    assert "1d summary: start=2024-02-05, end=2024-02-06" in result.stdout
    assert "1min summary: already current through 2024-02-06" in result.stdout
    assert "update run complete: duration_seconds=" in result.stdout


def test_update_cli_accepts_repeatable_freq(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    def fake_run_incremental_update(**kwargs):
        captured.update(kwargs)
        return UpdateResult(
            end=date(2024, 2, 6),
            frequencies=[FrequencyUpdateResult(freq="1d", start=None, end=None)],
            synced_reference_data=True,
            corporate_actions_start=None,
        )

    monkeypatch.setattr(
        "equity_data_stack.cli.run_incremental_update",
        fake_run_incremental_update,
    )

    result = CliRunner().invoke(
        app,
        [
            "update",
            "--freq",
            "1d",
            "--data-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert captured["freqs"] == ["1d"]
    assert captured["write_universe"] is True
    assert captured["event_logger"] is not None


def test_update_cli_logs_failure(monkeypatch, tmp_path: Path) -> None:
    def fake_run_incremental_update(**kwargs):
        raise ValueError("No completed ingestion found for freq=1d")

    monkeypatch.setattr(
        "equity_data_stack.cli.run_incremental_update",
        fake_run_incremental_update,
    )

    result = CliRunner().invoke(
        app,
        ["update", "--data-root", str(tmp_path)],
    )

    assert result.exit_code != 0
    assert "update run failed: ValueError: No completed ingestion found" in result.stdout


def test_log_tail_cli_prints_recent_rows(tmp_path: Path) -> None:
    log = IngestionLog(tmp_path)
    log.record(date(2024, 1, 2), "1d", "complete")
    log.record(date(2024, 1, 3), "1d", "failed")

    result = CliRunner().invoke(
        app,
        ["log-tail", "--limit", "1", "--data-root", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert "2024-01-03" in result.stdout
    assert "failed" in result.stdout
    assert "2024-01-02" not in result.stdout
