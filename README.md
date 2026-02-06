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

# Sync reference tables via REST
equity-stack sync-security-master
equity-stack sync-corporate-actions --start 2020-01-01 --end 2020-12-31

# Build split/dividend tables
equity-stack build-corporate-actions-tables --start 2020-01-01 --end 2020-12-31

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

## Status
Early implementation per `spec.md`. Expect breaking changes while core interfaces settle.
