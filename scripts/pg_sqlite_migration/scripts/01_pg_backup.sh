#!/usr/bin/env bash
set -euo pipefail

: "${PG_URL:?Set PG_URL to your PostgreSQL connection string}"
BACKUP_DIR=${BACKUP_DIR:-migration_workspace/backup}
mkdir -p "$BACKUP_DIR"

ts=$(date +%Y%m%d%H%M%S)
outfile="$BACKUP_DIR/pg_backup_${ts}.dump"

echo "Creating PostgreSQL backup at $outfile"
pg_dump --format=custom --file="$outfile" "$PG_URL"

echo "Backup complete."
