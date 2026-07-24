#!/usr/bin/env bash
set -euo pipefail

START_DATE="2021-02-10"
END_DATE="2022-01-01"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_cmd equity-stack

echo "Backfill start: ${START_DATE} -> ${END_DATE}"

echo "Sync daily flat files"
equity-stack sync-flat-files --start "${START_DATE}" --end "${END_DATE}" --prefix us_stocks_sip/day_aggs_v1

echo "Ingest daily bars + universe snapshots"
equity-stack sync --freq 1d --start "${START_DATE}" --end "${END_DATE}" --write-universe

echo "Sync 1-minute flat files"
equity-stack sync-flat-files --start "${START_DATE}" --end "${END_DATE}" --prefix us_stocks_sip/minute_aggs_v1

echo "Ingest 1-minute bars"
equity-stack sync --freq 1min --start "${START_DATE}" --end "${END_DATE}"

echo "Sync security master (REST)"
equity-stack sync-security-master

echo "Sync corporate actions (REST, scoped)"
equity-stack sync-corporate-actions --start "${START_DATE}" --end "${END_DATE}"

echo "Build split/dividend tables"
equity-stack build-corporate-actions-tables --start "${START_DATE}" --end "${END_DATE}"

echo "Backfill complete"
