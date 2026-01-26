#!/usr/bin/env bash
set -euo pipefail

: "${PG_URL:?Set PG_URL to your PostgreSQL connection string}"
SQLITE_PATH=${SQLITE_PATH:-db.sqlite3.new}
REPORT_DIR=${REPORT_DIR:-migration_workspace/reports}
PYTHON_BIN=${PYTHON_BIN:-python}

mkdir -p "$REPORT_DIR"

echo "Running validation suite"
$PYTHON_BIN tests/run_all_tests.py \
  --pg "$PG_URL" \
  --sqlite "$SQLITE_PATH" \
  --report "$REPORT_DIR/summary.md"

echo "Validation reports written to $REPORT_DIR"
