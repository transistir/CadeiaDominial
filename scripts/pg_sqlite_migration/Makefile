PYTHON ?= python
SQLITE_PATH ?= db.sqlite3.new
PG_URL ?=

.PHONY: env backup schema preprocess copy fixups validate all

env:
	scripts/00_env_check.sh

backup:
	PG_URL=$(PG_URL) scripts/01_pg_backup.sh

schema:
	SQLITE_PATH=$(SQLITE_PATH) PYTHON_BIN=$(PYTHON) scripts/02_schema_sqlite.sh

preprocess:
	psql "$(PG_URL)" -f scripts/03_pg_preprocess.sql

copy:
	PG_URL=$(PG_URL) SQLITE_PATH=$(SQLITE_PATH) $(PYTHON) scripts/04_copy_db_to_sqlite.py --pg "$(PG_URL)" --sqlite "$(SQLITE_PATH)"

fixups:
	SQLITE_PATH=$(SQLITE_PATH) PYTHON_BIN=$(PYTHON) scripts/05_post_import_fixups.sh

validate:
	PG_URL=$(PG_URL) SQLITE_PATH=$(SQLITE_PATH) PYTHON_BIN=$(PYTHON) scripts/06_validate.sh

all: env backup schema preprocess copy fixups validate
