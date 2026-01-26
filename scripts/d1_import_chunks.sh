#!/usr/bin/env bash
set -euo pipefail

CHUNK_LINES=${CHUNK_LINES:-10000}
DB_NAME=${DB_NAME:-cadeia-dominial}
SCHEMA_FILE=${SCHEMA_FILE:-schema.cleaned.core.no-auth.no-fk.sql}
DATA_FILE=${DATA_FILE:-data.cleaned.core.no-auth.sql}
WRANGLER_CMD=${WRANGLER_CMD:-"cfd wrangler"}
CONFIG_PATH=${CONFIG_PATH:-packages/api/wrangler.toml}

if ! command -v ${WRANGLER_CMD%% *} >/dev/null 2>&1; then
  echo "Error: '${WRANGLER_CMD%% *}' not found. Set WRANGLER_CMD or install it." >&2
  exit 1
fi

if [[ ! -f "$SCHEMA_FILE" ]]; then
  echo "Error: schema file not found: $SCHEMA_FILE" >&2
  exit 1
fi

if [[ ! -f "$DATA_FILE" ]]; then
  echo "Error: data file not found: $DATA_FILE" >&2
  exit 1
fi

CHUNK_DIR=".d1_chunks"
rm -rf "$CHUNK_DIR"
mkdir -p "$CHUNK_DIR"

split -l "$CHUNK_LINES" -a 3 "$DATA_FILE" "$CHUNK_DIR/data.chunk."

${WRANGLER_CMD} d1 execute "$DB_NAME" --file "$SCHEMA_FILE" --config "$CONFIG_PATH" --remote

for f in "$CHUNK_DIR"/data.chunk.*; do
  echo "Importing $f"
  ${WRANGLER_CMD} d1 execute "$DB_NAME" --file "$f" --config "$CONFIG_PATH" --remote
  echo "OK: $f"
 done

