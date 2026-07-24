# Equity Data Stack

Local-first data infrastructure for US equity research. The stack ingests Massive (Polygon) bulk exports, stores them as partitioned Parquet, and queries them through DuckDB for fast, cheap analytics on a single workstation.

## Features
- Bulk ingestion with resumable logging
- Hive-partitioned Parquet layout for daily and 1-minute bars
- DuckDB-powered `load_prices` API for wide panel data
- Pluggable provider interface (Polygon today, others later)

## Project Layout
```
DATA_ROOT/
├── security_master.parquet
├── corporate_actions/
│   ├── splits.parquet
│   ├── dividends.parquet
│   ├── split_ratios.parquet
│   └── cash_dividends.parquet
├── universe/
│   └── snapshots/date=YYYY-MM-DD.parquet
├── bars/
│   ├── freq=1d/year=YYYY/YYYY.parquet
│   └── freq=1min/year=YYYY/month=MM/day=YYYY-MM-DD.parquet
└── logs/ingestion_log.parquet
```

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Environment variables (see `.env.example`):
- `DATA_ROOT` (required for storage)
- `MASSIVE_ACCESS_KEY` / `MASSIVE_SECRET_KEY` (required for flat-file sync)
- `MASSIVE_S3_ENDPOINT` / `MASSIVE_S3_BUCKET` / `MASSIVE_S3_PREFIX` (required for flat-file sync)
- `POLYGON_API_KEY` (required for security master / corporate actions)

## CLI Usage
```bash
# Sync flat files from Massive S3 (trading days only)
equity-stack sync-flat-files --start 2020-01-01 --end 2020-12-31 \
  --prefix us_stocks_sip/day_aggs_v1

# Ingest bars into Parquet + universe snapshots
equity-stack sync --freq 1d --start 2020-01-01 --end 2020-12-31 --write-universe

# Ingest 1-minute bars into Parquet
equity-stack sync --freq 1min --start 2020-01-01 --end 2020-12-31

# Incrementally sync from the latest completed ingestion through the previous trading day
equity-stack update

# First update, or if a frequency has no completed log history yet
equity-stack update --start 2020-01-01

# Inspect recent ingestion events without opening Python
equity-stack log-tail --limit 30

# Sync reference tables via REST
equity-stack sync-security-master
equity-stack sync-corporate-actions --start 2020-01-01 --end 2020-12-31

# Build split/dividend tables
equity-stack build-corporate-actions-tables --start 2020-01-01 --end 2020-12-31

```

## Incremental Updates
`equity-stack update` is the normal command for keeping the local data lake current.
It reads `DATA_ROOT/logs/ingestion_log.parquet`, finds the latest completed date for
each frequency, downloads missing Massive flat files, ingests them into Parquet, and
refreshes security master and corporate action tables.

The default end date is the previous NYSE trading day. By default the command updates
both daily and 1-minute bars:
```bash
equity-stack update
```

Useful variants:
```bash
equity-stack update --freq 1d
equity-stack update --end 2026-07-21
equity-stack update --skip-reference-data
```

The Parquet ingestion log remains the source of truth. A CSV mirror is also written at
`DATA_ROOT/logs/ingestion_log.csv` so it can be inspected with normal shell tools:
```bash
tail -n 30 DATA_ROOT/logs/ingestion_log.csv
```

## Nightly Automation
On macOS, install the local LaunchAgent:
```bash
scripts/install_launchd_update.sh
```

It runs daily at 06:30 local time from this repo using `.venv/bin/equity-stack update`.
Automation stdout/stderr logs are written under `DATA_ROOT/logs/automation/`.
The update output is timestamped and includes resolved date windows, per-frequency raw
download counts, Parquet ingest counts, reference-data status, and failure details.

Inspect automation logs:
```bash
tail -n 100 DATA_ROOT/logs/automation/update.out.log
tail -n 100 DATA_ROOT/logs/automation/update.err.log
```

Uninstall:
```bash
scripts/install_launchd_update.sh uninstall
```

## Python API
```python
from datetime import datetime
from equity_data_stack import load_prices

prices = load_prices(
    freq="1d",
    symbols=["AAPL", "MSFT"],
    start=datetime(2022, 1, 1),
    end=datetime(2022, 12, 31),
    fields=["close"],
)

from equity_data_stack import (
    apply_price_adjustments,
    load_dividend_cash_table,
    load_split_ratio_table,
)

split_ratios = load_split_ratio_table(
    data_root="DATA_ROOT",
    start=datetime(2022, 1, 1).date(),
    end=datetime(2022, 12, 31).date(),
    symbols=["AAPL", "MSFT"],
)
dividend_cash = load_dividend_cash_table(
    data_root="DATA_ROOT",
    start=datetime(2022, 1, 1).date(),
    end=datetime(2022, 12, 31).date(),
    symbols=["AAPL", "MSFT"],
)
adjusted = apply_price_adjustments(prices, split_ratios, dividend_cash)

# Or load adjusted prices/volumes directly
from equity_data_stack import load_adjusted_prices, load_adjusted_volumes

adj_prices = load_adjusted_prices(
    data_root="DATA_ROOT",
    freq="1d",
    symbols=["AAPL", "MSFT"],
    start=datetime(2022, 1, 1),
    end=datetime(2022, 12, 31),
)
adj_volume = load_adjusted_volumes(
    data_root="DATA_ROOT",
    freq="1d",
    symbols=["AAPL", "MSFT"],
    start=datetime(2022, 1, 1),
    end=datetime(2022, 12, 31),
)
```

## Development
- Lint: `ruff check .`
- Tests: `pytest`
- Format: `ruff check . --fix` (optional)
