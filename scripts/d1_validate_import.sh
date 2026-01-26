#!/usr/bin/env bash
set -euo pipefail

SCHEMA_FILE=${SCHEMA_FILE:-schema.cleaned.core.no-auth.no-fk.sql}
DATA_FILE=${DATA_FILE:-data.cleaned.core.no-auth.sql}
DB_PATH=${DB_PATH:-/tmp/d1_import_test.db}

if [[ ! -f "$SCHEMA_FILE" ]]; then
  echo "Error: schema file not found: $SCHEMA_FILE" >&2
  exit 1
fi

if [[ ! -f "$DATA_FILE" ]]; then
  echo "Error: data file not found: $DATA_FILE" >&2
  exit 1
fi

rm -f "$DB_PATH"

sqlite3 "$DB_PATH" ".read $SCHEMA_FILE"
sqlite3 "$DB_PATH" ".read $DATA_FILE"

sqlite3 "$DB_PATH" "SELECT count(*) AS tables FROM sqlite_master WHERE type='table';"

