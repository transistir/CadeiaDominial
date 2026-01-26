#!/usr/bin/env bash
set -euo pipefail

: "${DJANGO_SETTINGS_MODULE:?Set DJANGO_SETTINGS_MODULE for manage.py}"
PYTHON_BIN=${PYTHON_BIN:-python}
SQLITE_PATH=${SQLITE_PATH:-db.sqlite3.new}

export SQLITE_PATH
export DJANGO_SETTINGS_MODULE

echo "Running Django migrations against $SQLITE_PATH"
$PYTHON_BIN manage.py migrate --run-syncdb --database=sqlite

echo "Ensure SQLite PRAGMAs (set in settings.py OPTIONS): foreign_keys=ON, journal_mode=WAL"
$PYTHON_BIN tests/02_schema_tests.py --sqlite "$SQLITE_PATH" --skip-pg

echo "Schema migration complete."
