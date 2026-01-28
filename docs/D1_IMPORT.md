# D1 Import Playbook

This guide documents the repeatable process for importing the legacy SQLite data into Cloudflare D1.

## Source

- Source SQLite DB: `db.sqlite3.new`

## Output Files (generated)

- `schema.cleaned.core.no-auth.no-fk.sql` — schema with Django/auth removed and foreign keys stripped.
- `data.cleaned.core.no-auth.no-unistr.sql` — data with Django/auth removed and `unistr(...)` converted.
- `.d1_chunks/` — chunked data files for remote import (temporary; do not commit).

## Why the cleanup steps

- D1 does not allow `sqlite_sequence` or certain pragma/transaction statements.
- D1 does not support SQLite `unistr(...)` function.
- Legacy Django tables (`django_*`, `auth_*`) are not part of the new architecture.
- Foreign keys are stripped to allow bulk import without constraint failures.

## 1) Build schema + data from the SQLite DB

```bash
# Export schema and data
sqlite3 db.sqlite3.new ".schema" > schema.sql
sqlite3 db.sqlite3.new ".dump --data-only" > data.sql

# Remove transaction/pragma lines
rg -v "^(BEGIN TRANSACTION|COMMIT|ROLLBACK|SAVEPOINT|RELEASE|PRAGMA)" schema.sql > schema.cleaned.sql
rg -v "^(BEGIN TRANSACTION|COMMIT|ROLLBACK|SAVEPOINT|RELEASE|PRAGMA)" data.sql > data.cleaned.sql

# If you don't have rg installed, use grep instead
grep -Ev "^(BEGIN TRANSACTION|COMMIT|ROLLBACK|SAVEPOINT|RELEASE|PRAGMA)" schema.sql > schema.cleaned.sql
grep -Ev "^(BEGIN TRANSACTION|COMMIT|ROLLBACK|SAVEPOINT|RELEASE|PRAGMA)" data.sql > data.cleaned.sql
```

## 2) Remove Django/auth tables + references

```bash
# Remove Django/auth tables + indexes, and strip FK refs
python - <<'PY'
from pathlib import Path
import re

src = Path('schema.cleaned.sql')
text = src.read_text()

out_lines = []
for line in text.splitlines():
    if re.search(r'CREATE (UNIQUE )?INDEX "(auth_|django_)', line):
        continue
    if re.search(r'CREATE TABLE IF NOT EXISTS "(auth_|django_)', line):
        continue

    line = re.sub(r' REFERENCES "(auth_|django_)[^"]+" \("[^"]+"\) DEFERRABLE INITIALLY DEFERRED', '', line)

    out_lines.append(line)

Path('schema.cleaned.core.no-auth.sql').write_text("\n".join(out_lines) + "\n")
PY

# Remove Django/auth data rows
rg -v "auth_|django_" data.cleaned.sql > data.cleaned.core.no-auth.sql
```

## 3) Strip foreign keys entirely (for bulk import)

```bash
python - <<'PY'
from pathlib import Path
import re

src = Path('schema.cleaned.core.no-auth.sql')
text = src.read_text()

text = re.sub(r'\s+REFERENCES\s+"[^"]+"\s*\("[^"]+"\)\s*DEFERRABLE\s+INITIALLY\s+DEFERRED', '', text)
text = re.sub(r'\s+REFERENCES\s+"[^"]+"\s*\("[^"]+"\)', '', text)

Path('schema.cleaned.core.no-auth.no-fk.sql').write_text(text)
PY
```

## 3b) Remove sqlite_sequence (reserved in D1)

```bash
python - <<'PY'
from pathlib import Path

src = Path('schema.cleaned.core.no-auth.no-fk.sql')
lines = [ln for ln in src.read_text().splitlines() if 'sqlite_sequence' not in ln]
src.write_text("\n".join(lines) + "\n")
PY
```

## 4) Convert SQLite `unistr(...)` calls

```bash
python - <<'PY'
from pathlib import Path
import re

src = Path('data.cleaned.core.no-auth.sql')
text = src.read_text()

pattern = re.compile(r"unistr\('((?:[^']|''|\\u[0-9a-fA-F]{4})*)'\)")

def replace(match):
    s = match.group(1)
    s = s.replace("''", "'")
    def decode_unicode(m):
        return chr(int(m.group(1), 16))
    s = re.sub(r"\\u([0-9a-fA-F]{4})", decode_unicode, s)
    s = s.replace("'", "''")
    return f"'{s}'"

new_text, _ = pattern.subn(replace, text)
Path('data.cleaned.core.no-auth.no-unistr.sql').write_text(new_text)
PY
```

## 5) Local validation (optional but recommended)

```bash
./scripts/d1_validate_import.sh \
  SCHEMA_FILE=schema.cleaned.core.no-auth.no-fk.sql \
  DATA_FILE=data.cleaned.core.no-auth.no-unistr.sql
```

## 6) Remote import (chunked)

```bash
# Reset target tables/indexes (optional but useful on re-import)
wrangler d1 execute cadeia-dominial --file schema.drop.sql --config packages/api/wrangler.toml --remote

# Import schema + chunked data
SCHEMA_FILE=schema.cleaned.core.no-auth.no-fk.sql \
DATA_FILE=data.cleaned.core.no-auth.no-unistr.sql \
WRANGLER_CMD="wrangler" \
./scripts/d1_import_chunks.sh
```

## 7) Verification

```bash
wrangler d1 execute cadeia-dominial \
  --command "SELECT count(*) AS total_documentos FROM dominial_documento;" \
  --config packages/api/wrangler.toml --remote
```

## Cleanup

After a successful import, remove intermediate files and chunk output. Keep the
two final artifacts (`schema.cleaned.core.no-auth.no-fk.sql` and
`data.cleaned.core.no-auth.no-unistr.sql`) if you plan to re-import without
re-deriving them.

```bash
rm -rf .d1_chunks
rm -f schema.sql data.sql schema.cleaned.sql data.cleaned.sql \
  schema.cleaned.core.no-auth.sql data.cleaned.core.no-auth.sql
```
