#!/usr/bin/env bash
set -euo pipefail

SQLITE_PATH=${SQLITE_PATH:-db.sqlite3.new}
PYTHON_BIN=${PYTHON_BIN:-python}

echo "Reapplying PRAGMAs to $SQLITE_PATH"
sqlite3 "$SQLITE_PATH" "PRAGMA foreign_keys=ON; PRAGMA journal_mode=WAL;"

echo "Rebuilding indexes/migrations for SQLite"
$PYTHON_BIN manage.py migrate --database=sqlite

echo "Running quick FK check"
sqlite3 "$SQLITE_PATH" "PRAGMA foreign_key_check;"

echo "Post-import fixups complete."
