# PostgreSQL → SQLite Migration Runbook

This runbook makes the migration reproducible with one command (`make all`) or step-by-step scripts. Adjust env vars (see `config/env.example`) before running.

## Prerequisites
- Tools: `python`, `pip`, `pg_dump`, `psql`, `sqlite3`
- Python deps: `django`, `psycopg2-binary`, `pyyaml` (if you use YAML parsing)
- Set `PG_URL`, `SQLITE_PATH`, `DJANGO_SETTINGS_MODULE` in your environment or `.env`

## One-shot run
```bash
make all PG_URL=$PG_URL SQLITE_PATH=db.sqlite3.new
```

## Manual steps
0) (Optional) Start local user-owned Postgres (matches what was run)
   ```bash
   /usr/lib/postgresql/14/bin/initdb -D .pgdata -E UTF8 --locale=en_US.UTF-8 --no-instructions --username=pguser --pwfile=<(echo pgpass)
   perl -0777 -pe "s/^#?listen_addresses.*/listen_addresses=''/; s/^#?port.*/port = 55432/" -i .pgdata/postgresql.conf
   /usr/lib/postgresql/14/bin/pg_ctl -D .pgdata -o "-k $(pwd)/.pgdata" -l .pgdata/postgres.log start
   export PG_URL="postgresql:///cadeiadominial?host=$(pwd)/.pgdata&port=55432&user=pguser"
   createdb "$PG_URL" || true
   psql "$PG_URL" -f backup_cadeiadominial.sql
   ```

1) Env check  
   `scripts/00_env_check.sh`

2) Backup PostgreSQL  
   `PG_URL=$PG_URL scripts/01_pg_backup.sh`

3) Create SQLite schema via Django  
   `SQLITE_PATH=db.sqlite3.new scripts/02_schema_sqlite.sh`

4) Preprocess data in PostgreSQL (UTC timestamps, scaled numerics)  
   `psql "$PG_URL" -f scripts/03_pg_preprocess.sql`

5) Copy data FK-aware with bundled Python copier
   `PG_URL=$PG_URL SQLITE_PATH=db.sqlite3.new python scripts/04_copy_db_to_sqlite.py --pg "$PG_URL" --sqlite "$SQLITE_PATH"`

6) Post-import fixups (PRAGMAs, indexes)  
   `SQLITE_PATH=db.sqlite3.new scripts/05_post_import_fixups.sh`

7) Validation suite + report  
   `PG_URL=$PG_URL SQLITE_PATH=db.sqlite3.new scripts/06_validate.sh`

8) Switch Django to SQLite and run app tests  
   `python manage.py test`

## Configuration
- `config/env.example`: copy to `.env` and fill in secrets/paths.
- `config/tables.yaml`: table order and optional view mappings (`source_table: view_name`) if you use preprocessing views.

## Expected artifacts
- Backups: `migration_workspace/backup/pg_backup_*.dump`
- Logs: `migration_workspace/logs/`
- Reports: `migration_workspace/reports/summary.md`
- Target DB: `db.sqlite3.new`

## Current run status (documented)
- Date: 2026-01-26
- Source restored from: `backup_cadeiadominial.sql` into local cluster `.pgdata` (socket + port 55432, user `pguser`)
- Target produced: `db.sqlite3.new`
- Validation: all PASS (`migration_workspace/reports/summary.md`)
- Data loss: 0 rows (counts + checksums matched)
- FK integrity: clean

## Notes
- Keep SQLite `OPTIONS` in Django: `init_command="PRAGMA foreign_keys=ON; PRAGMA journal_mode=WAL;"`.
- If write load exceeds single-writer limits, stop before cutover and reconsider the target DB.
