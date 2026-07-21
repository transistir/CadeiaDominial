# Schema Improvement Proposal

## Executive Summary

This document proposes simplifications to the Cadeia Dominial database schema to:
1. Reduce complexity and maintenance burden
2. Enable migration from PostgreSQL to SQLite
3. Remove legacy/redundant fields
4. Consolidate over-normalized tables

**Estimated reduction: 19 tables → 11 tables (42% reduction)**

---

## Table of Contents

1. [Current Schema Analysis](#current-schema-analysis)
2. [Identified Issues](#identified-issues)
3. [Proposed Simplifications](#proposed-simplifications)
4. [SQLite Compatibility Changes](#sqlite-compatibility-changes)
5. [Proposed Schema (v2)](#proposed-schema-v2)
6. [Migration Path](#migration-path)
7. [Migration Scripts](#migration-scripts)
8. [Rollback Strategy](#rollback-strategy)

---

## Current Schema Analysis

### Current Table Count: 19 Tables

| Category | Tables | Purpose |
|----------|--------|---------|
| Core | `tis`, `terraindigenareferencia`, `tis_imovel` | Indigenous lands |
| People | `pessoas` | Persons |
| Registry | `cartorios`, `importacaocartorios` | Registry offices |
| Property | `imovel` | Properties |
| Documents | `documento`, `documentotipo`, `documentoimportado` | Documents |
| Recordings | `lancamento`, `lancamentotipo`, `lancamentopessoa`, `origemfimcadeia`, `fimcadeia` | Transactions |
| Amendments | `alteracoes`, `alteracoestipo`, `registrotipo`, `averbacaotipo` | Changes |

---

## Identified Issues

### 1. Legacy Fields (Technical Debt)

**`lancamento` table has deprecated fields:**

| Field | Issue | Recommendation |
|-------|-------|----------------|
| `transmitente_id` | Replaced by `lancamentopessoa` table | Remove |
| `adquirente_id` | Replaced by `lancamentopessoa` table | Remove |
| `cartorio_transacao_id` | Replaced by `cartorio_transmissao_id` | Remove |

**Evidence from migrations:**
- Migration `0029_sync_cartorio_transmissao_data.py` copied data from `cartorio_transacao` to `cartorio_transmissao`
- Migration `0010_lancamentopessoa.py` introduced the many-to-many relationship

### 2. Over-Normalized Lookup Tables

**Small lookup tables with 2-3 fixed values:**

| Table | Values | Recommendation |
|-------|--------|----------------|
| `documentotipo` | `matricula`, `transcricao` | Use CHECK constraint |
| `lancamentotipo` | `averbacao`, `registro`, `inicio_matricula` | Keep (has business rules) |
| `alteracoestipo` | `registro`, `averbacao`, `nao_classificado` | Use CHECK constraint |
| `registrotipo` | Dynamic user entries | Keep |
| `averbacaotipo` | Dynamic user entries | Keep |

### 3. Redundant Junction Table

**`tis_imovel` junction table:**
- `imovel` already has `terra_indigena_id_id` foreign key
- Junction table creates M:N but actual usage appears to be 1:N
- **Recommendation:** Verify usage; if truly 1:N, remove junction table

### 4. Duplicate Functionality

**`alteracoes` vs `lancamento`:**

Both tables track property changes with similar fields:
- `livro`, `folha`, `cartorio`
- `transmitente`, `adquirente`
- `valor_transacao`, `area`
- `observacoes`, `data_cadastro`

**Key differences:**
- `alteracoes` is document-independent
- `lancamento` is attached to `documento`

**Recommendation:** Keep both but clarify use cases in documentation

### 5. Complex End-of-Chain Structure

**Current structure (3 tables):**
- `origemfimcadeia` - Per-origin end-of-chain data
- `fimcadeia` - Master list of end types
- `documento.classificacao_fim_cadeia` - Document-level classification

**Issue:** Over-engineered for the actual use case

**Recommendation:** Simplify to single table approach

---

## Proposed Simplifications

### Summary of Changes

| Change | Current | Proposed | Savings |
|--------|---------|----------|---------|
| Remove `documentotipo` table | Separate table | VARCHAR + CHECK | 1 table |
| Remove `alteracoestipo` table | Separate table | VARCHAR + CHECK | 1 table |
| Remove `tis_imovel` junction | M:N table | Use existing FK | 1 table |
| Remove legacy fields | 3 fields in `lancamento` | Delete columns | Cleaner schema |
| Merge `origemfimcadeia` | Separate table | Inline in `lancamento` | 1 table |
| Remove `importacaocartorios` | Admin tracking | Move to logs | 1 table |
| Remove `alteracoes` + related | 3 tables | Merge into `lancamento` | 3 tables |
| Simplify `lancamentotipo` | 10 boolean fields | 4 key fields | Cleaner |

**Total: 8 tables removed (19 → 11)**

---

## SQLite Compatibility Changes

### PostgreSQL → SQLite Differences

| Feature | PostgreSQL | SQLite | Migration |
|---------|-----------|--------|-----------|
| SERIAL | `SERIAL` | `INTEGER PRIMARY KEY AUTOINCREMENT` | Auto-handled |
| VARCHAR(n) | Enforced length | Not enforced | Use CHECK if needed |
| DECIMAL | Full precision | Stored as REAL | Accept or use INTEGER cents |
| TIMESTAMP | `TIMESTAMP` | `TEXT` (ISO8601) | Format conversion |
| BOOLEAN | Native | `INTEGER` (0/1) | Auto-handled |
| Arrays | Native | Not supported | Use JSON or separate table |
| Enums | `CREATE TYPE` | Not supported | Use CHECK constraints |
| UUID | `uuid-ossp` extension | Not supported | Use TEXT |
| Full-text search | `pg_trgm` | FTS5 | Different syntax |
| Concurrent writes | MVCC | File locking | Application-level handling |

### Required Changes

```sql
-- PostgreSQL ENUM becomes CHECK constraint
-- Before:
CREATE TYPE cartorio_tipo AS ENUM ('CRI', 'OUTRO');

-- After (SQLite compatible):
CREATE TABLE cartorios (
    tipo TEXT NOT NULL DEFAULT 'CRI'
    CHECK (tipo IN ('CRI', 'OUTRO'))
);
```

### Date/Time Handling

```sql
-- Store as ISO8601 text in SQLite
-- Example: '2024-01-15' for DATE, '2024-01-15T10:30:00' for TIMESTAMP

-- Query pattern change:
-- PostgreSQL: WHERE data >= '2024-01-01'::date
-- SQLite:     WHERE data >= '2024-01-01'
```

---

## Proposed Schema (v2)

### Table Count: 11 Tables (down from 19)

### Tables to Keep (Modified)

#### 1. `pessoas` (unchanged)
```sql
CREATE TABLE pessoas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    cpf TEXT UNIQUE,
    rg TEXT,
    data_nascimento TEXT,  -- ISO8601 date
    email TEXT,
    telefone TEXT
);
```

#### 2. `cartorios` (unchanged)
```sql
CREATE TABLE cartorios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    cns TEXT NOT NULL UNIQUE,
    endereco TEXT,
    telefone TEXT,
    email TEXT,
    estado TEXT,
    cidade TEXT,
    tipo TEXT NOT NULL DEFAULT 'CRI' CHECK (tipo IN ('CRI', 'OUTRO'))
);
```

#### 3. `terra_indigena_referencia` (unchanged)
```sql
CREATE TABLE terra_indigena_referencia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL,
    etnia TEXT,
    estado TEXT,
    municipio TEXT,
    area_ha REAL,
    fase TEXT,
    modalidade TEXT,
    coordenacao_regional TEXT,
    data_regularizada TEXT,
    data_homologada TEXT,
    data_declarada TEXT,
    data_delimitada TEXT,
    data_em_estudo TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

#### 4. `tis` (unchanged)
```sql
CREATE TABLE tis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    terra_referencia_id INTEGER REFERENCES terra_indigena_referencia(id),
    nome TEXT NOT NULL,
    codigo TEXT NOT NULL UNIQUE,
    etnia TEXT NOT NULL,
    estado TEXT,
    area REAL,
    data_cadastro TEXT NOT NULL DEFAULT (date('now'))
);
```

#### 5. `imovel` (unchanged)
```sql
CREATE TABLE imovel (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    terra_indigena_id INTEGER NOT NULL REFERENCES tis(id),
    nome TEXT NOT NULL,
    proprietario_id INTEGER NOT NULL REFERENCES pessoas(id),
    matricula TEXT NOT NULL,
    tipo_documento TEXT NOT NULL DEFAULT 'matricula'
        CHECK (tipo_documento IN ('matricula', 'transcricao')),
    observacoes TEXT,
    cartorio_id INTEGER REFERENCES cartorios(id),
    data_cadastro TEXT NOT NULL DEFAULT (date('now')),
    arquivado INTEGER NOT NULL DEFAULT 0,
    UNIQUE (matricula, cartorio_id)
);
CREATE INDEX idx_imovel_matricula_cartorio ON imovel(matricula, cartorio_id);
```

#### 6. `documento` (simplified - inline tipo)
```sql
CREATE TABLE documento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    imovel_id INTEGER NOT NULL REFERENCES imovel(id) ON DELETE CASCADE,
    -- CHANGE: Inline tipo instead of FK
    tipo TEXT NOT NULL CHECK (tipo IN ('matricula', 'transcricao')),
    numero TEXT NOT NULL,
    data TEXT NOT NULL,
    cartorio_id INTEGER NOT NULL REFERENCES cartorios(id),
    livro TEXT NOT NULL,
    folha TEXT NOT NULL,
    origem TEXT,
    observacoes TEXT,
    data_cadastro TEXT NOT NULL DEFAULT (date('now')),
    nivel_manual INTEGER,
    classificacao_fim_cadeia TEXT
        CHECK (classificacao_fim_cadeia IN ('origem_lidima', 'sem_origem', 'inconclusa')),
    sigla_patrimonio_publico TEXT,
    cri_atual_id INTEGER REFERENCES cartorios(id),
    cri_origem_id INTEGER REFERENCES cartorios(id),
    UNIQUE (numero, cartorio_id)
);
```

#### 7. `documento_importado` (unchanged)
```sql
CREATE TABLE documento_importado (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    documento_id INTEGER NOT NULL REFERENCES documento(id) ON DELETE CASCADE,
    imovel_origem_id INTEGER NOT NULL REFERENCES imovel(id) ON DELETE CASCADE,
    data_importacao TEXT NOT NULL DEFAULT (datetime('now')),
    importado_por_id INTEGER,  -- FK to auth_user if using Django
    UNIQUE (documento_id, imovel_origem_id)
);
```

#### 8. `lancamento_tipo` (simplified - fewer booleans)
```sql
CREATE TABLE lancamento_tipo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL CHECK (tipo IN ('averbacao', 'registro', 'inicio_matricula')),
    -- Simplified: group related requirements
    requer_transmissao INTEGER NOT NULL DEFAULT 0,
    requer_cartorio_origem INTEGER NOT NULL DEFAULT 0,
    requer_titulo INTEGER NOT NULL DEFAULT 0,
    requer_descricao INTEGER NOT NULL DEFAULT 0
);
```

#### 9. `lancamento` (simplified - removed legacy fields)
```sql
CREATE TABLE lancamento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    documento_id INTEGER NOT NULL REFERENCES documento(id) ON DELETE CASCADE,
    tipo_id INTEGER NOT NULL REFERENCES lancamento_tipo(id),
    numero_lancamento TEXT,
    data TEXT NOT NULL,
    -- REMOVED: transmitente_id, adquirente_id (use lancamento_pessoa)
    -- REMOVED: cartorio_transacao_id (legacy, use cartorio_transmissao_id)
    valor_transacao REAL,
    area REAL,
    origem TEXT,
    detalhes TEXT,
    observacoes TEXT,
    data_cadastro TEXT NOT NULL DEFAULT (date('now')),
    forma TEXT,
    descricao TEXT,
    titulo TEXT,
    cartorio_origem_id INTEGER REFERENCES cartorios(id),
    cartorio_transmissao_id INTEGER REFERENCES cartorios(id),
    livro_transacao TEXT,
    folha_transacao TEXT,
    data_transacao TEXT,
    livro_origem TEXT,
    folha_origem TEXT,
    data_origem TEXT,
    eh_inicio_matricula INTEGER NOT NULL DEFAULT 0,
    documento_origem_id INTEGER REFERENCES documento(id),
    -- NEW: Inline end-of-chain data (replaces origemfimcadeia for simple cases)
    fim_cadeia INTEGER NOT NULL DEFAULT 0,
    tipo_fim_cadeia TEXT CHECK (tipo_fim_cadeia IN ('destacamento_publico', 'outra', 'sem_origem')),
    classificacao_fim_cadeia TEXT
        CHECK (classificacao_fim_cadeia IN ('origem_lidima', 'sem_origem', 'inconclusa')),
    especificacao_fim_cadeia TEXT
);
```

#### 10. `lancamento_pessoa` (unchanged)
```sql
CREATE TABLE lancamento_pessoa (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lancamento_id INTEGER NOT NULL REFERENCES lancamento(id) ON DELETE CASCADE,
    pessoa_id INTEGER NOT NULL REFERENCES pessoas(id),
    tipo TEXT NOT NULL CHECK (tipo IN ('transmitente', 'adquirente')),
    nome_digitado TEXT,
    UNIQUE (lancamento_id, pessoa_id, tipo)
);
```

#### 11. `fim_cadeia` (master list - kept for dropdown values)
```sql
CREATE TABLE fim_cadeia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    tipo TEXT NOT NULL DEFAULT 'destacamento_publico'
        CHECK (tipo IN ('destacamento_publico', 'outra', 'sem_origem')),
    classificacao TEXT NOT NULL DEFAULT 'origem_lidima'
        CHECK (classificacao IN ('origem_lidima', 'sem_origem', 'inconclusa')),
    sigla TEXT,
    descricao TEXT,
    ativo INTEGER NOT NULL DEFAULT 1,
    data_criacao TEXT NOT NULL DEFAULT (datetime('now')),
    data_atualizacao TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### Tables Removed

| Table | Reason | Data Migration |
|-------|--------|----------------|
| `documentotipo` | Only 2 values | Inline CHECK constraint |
| `alteracoestipo` | Only 3 values | Inline CHECK constraint |
| `tis_imovel` | Redundant with `imovel.terra_indigena_id` | Verify M:N not needed |
| `origemfimcadeia` | Over-engineered | Merge into `lancamento` (see note below) |
| `importacaocartorios` | Admin/logging table | Move to application logs |
| `alteracoes` | Duplicate of `lancamento` | Migrate data to `lancamento` |
| `registrotipo` | Only used by `alteracoes` | Remove with `alteracoes` |
| `averbacaotipo` | Only used by `alteracoes` | Remove with `alteracoes` |

**Note on `origemfimcadeia` migration:** The inline approach in `lancamento` only supports single-origin cases. Before migration, verify that multi-origin cases (where `indice_origem > 0`) are rare or non-existent. If multi-origin cases exist, either:
1. Keep `origemfimcadeia` table for complex cases
2. Use a JSON field to store multiple origins
3. Create separate `lancamento` records for each origin

**Final Table Count: 11 Tables (down from 19) - 42% reduction**

---

## Migration Path

### Phase 1: Preparation (Non-Breaking)

```
Week 1: Preparation
├── Backup database
├── Document current data volumes
├── Create migration scripts
└── Test in staging environment
```

### Phase 2: Data Consolidation (PostgreSQL)

```
Week 2: Consolidate in PostgreSQL
├── Step 2.1: Remove legacy fields from lancamento
│   ├── Verify lancamento_pessoa has all transmitente/adquirente data
│   └── Drop columns: transmitente_id, adquirente_id, cartorio_transacao_id
│
├── Step 2.2: Inline documentotipo
│   ├── Add tipo column to documento
│   ├── Populate from documentotipo FK
│   └── Drop FK and documentotipo table
│
├── Step 2.3: Merge origemfimcadeia into lancamento
│   ├── Add fim_cadeia columns to lancamento
│   ├── Migrate data (only single-origin cases)
│   └── Keep origemfimcadeia for multi-origin (or use JSON)
│
└── Step 2.4: Evaluate alteracoes
    ├── Analyze if data should move to lancamento
    └── If keeping, inline alteracoestipo
```

### Phase 3: Export to SQLite

```
Week 3: SQLite Migration
├── Step 3.1: Create SQLite schema
├── Step 3.2: Export data with type conversions
│   ├── TIMESTAMP → TEXT (ISO8601)
│   ├── DECIMAL → REAL
│   └── BOOLEAN → INTEGER
├── Step 3.3: Verify data integrity
└── Step 3.4: Update application connection strings
```

### Phase 4: Validation

```
Week 4: Validation
├── Run application test suite
├── Verify all queries work
├── Performance testing
└── User acceptance testing
```

---

## Migration Scripts

### Script 1: Remove Legacy Fields from Lancamento

```sql
-- PostgreSQL Migration Script
-- Step 2.1: Remove legacy fields

-- Verify data is in lancamento_pessoa
SELECT COUNT(*) as lancamentos_with_legacy_transmitente
FROM dominial_lancamento
WHERE transmitente_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM dominial_lancamentopessoa
    WHERE lancamento_id = dominial_lancamento.id
      AND tipo = 'transmitente'
  );

-- If count > 0, migrate first:
INSERT INTO dominial_lancamentopessoa (lancamento_id, pessoa_id, tipo)
SELECT id, transmitente_id, 'transmitente'
FROM dominial_lancamento
WHERE transmitente_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM dominial_lancamentopessoa
    WHERE lancamento_id = dominial_lancamento.id
      AND tipo = 'transmitente'
  );

INSERT INTO dominial_lancamentopessoa (lancamento_id, pessoa_id, tipo)
SELECT id, adquirente_id, 'adquirente'
FROM dominial_lancamento
WHERE adquirente_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM dominial_lancamentopessoa
    WHERE lancamento_id = dominial_lancamento.id
      AND tipo = 'adquirente'
  );

-- Now safe to drop columns
ALTER TABLE dominial_lancamento DROP COLUMN transmitente_id;
ALTER TABLE dominial_lancamento DROP COLUMN adquirente_id;
ALTER TABLE dominial_lancamento DROP COLUMN cartorio_transacao_id;
```

### Script 2: Inline DocumentoTipo

```sql
-- Step 2.2: Inline documento tipo

-- Add new column
ALTER TABLE dominial_documento
ADD COLUMN tipo_inline VARCHAR(50);

-- Populate from FK
UPDATE dominial_documento d
SET tipo_inline = dt.tipo
FROM dominial_documentotipo dt
WHERE d.tipo_id = dt.id;

-- Add constraint
ALTER TABLE dominial_documento
ADD CONSTRAINT chk_tipo_documento
CHECK (tipo_inline IN ('matricula', 'transcricao'));

-- Make NOT NULL
ALTER TABLE dominial_documento
ALTER COLUMN tipo_inline SET NOT NULL;

-- Drop old FK
ALTER TABLE dominial_documento DROP COLUMN tipo_id;

-- Rename column
ALTER TABLE dominial_documento RENAME COLUMN tipo_inline TO tipo;

-- Drop old table
DROP TABLE dominial_documentotipo;
```

### Script 3: PostgreSQL to SQLite Export

```python
#!/usr/bin/env python3
"""
Export PostgreSQL database to SQLite
"""
import sqlite3
import psycopg2
from datetime import datetime, date
from decimal import Decimal

# Connection settings
PG_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'cadeia_dominial',
    'user': 'postgres',
    'password': ''
}

SQLITE_PATH = 'cadeia_dominial.db'

# Tables to migrate (in order for FK constraints)
# Note: Table names follow Django convention (no underscores in multi-word names)
TABLES = [
    'dominial_pessoas',
    'dominial_cartorios',
    'dominial_terraindigenareferencia',
    'dominial_tis',
    'dominial_imovel',
    'dominial_documento',
    'dominial_documentoimportado',     # Note: no underscore
    'dominial_lancamentotipo',          # Note: no underscore
    'dominial_lancamento',
    'dominial_lancamentopessoa',        # Note: no underscore
    'dominial_fimcadeia',               # Note: no underscore
]

def convert_value(val):
    """Convert PostgreSQL types to SQLite-compatible types"""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, date):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, bool):
        return 1 if val else 0
    return val

def migrate_table(pg_cur, sqlite_cur, table_name):
    """Migrate a single table from PostgreSQL to SQLite"""
    # Get column names
    pg_cur.execute(f"SELECT * FROM {table_name} LIMIT 0")
    columns = [desc[0] for desc in pg_cur.description]

    # Fetch all rows
    pg_cur.execute(f"SELECT * FROM {table_name}")
    rows = pg_cur.fetchall()

    if not rows:
        print(f"  {table_name}: 0 rows (empty)")
        return

    # Insert into SQLite
    placeholders = ', '.join(['?' for _ in columns])
    column_list = ', '.join(columns)
    insert_sql = f"INSERT INTO {table_name} ({column_list}) VALUES ({placeholders})"

    converted_rows = [
        tuple(convert_value(val) for val in row)
        for row in rows
    ]

    sqlite_cur.executemany(insert_sql, converted_rows)
    print(f"  {table_name}: {len(rows)} rows migrated")

def main():
    # Connect to PostgreSQL
    pg_conn = psycopg2.connect(**PG_CONFIG)
    pg_cur = pg_conn.cursor()

    # Connect to SQLite
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_cur = sqlite_conn.cursor()

    # Disable FK checks during migration
    sqlite_cur.execute("PRAGMA foreign_keys = OFF")

    print("Starting migration...")

    for table in TABLES:
        try:
            migrate_table(pg_cur, sqlite_cur, table)
        except Exception as e:
            print(f"  ERROR migrating {table}: {e}")

    # Re-enable FK checks
    sqlite_cur.execute("PRAGMA foreign_keys = ON")

    # Commit and close
    sqlite_conn.commit()
    sqlite_conn.close()
    pg_conn.close()

    print("Migration complete!")

if __name__ == '__main__':
    main()
```

### Script 4: Django Migration for Schema Changes

```python
# dominial/migrations/0050_simplify_schema.py

from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('dominial', '0042_fix_matricula_unique_constraint'),
    ]

    operations = [
        # Step 1: Migrate legacy transmitente/adquirente to lancamento_pessoa
        migrations.RunSQL(
            sql='''
            INSERT INTO dominial_lancamentopessoa (lancamento_id, pessoa_id, tipo)
            SELECT id, transmitente_id, 'transmitente'
            FROM dominial_lancamento
            WHERE transmitente_id IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM dominial_lancamentopessoa
                WHERE lancamento_id = dominial_lancamento.id
                  AND tipo = 'transmitente'
              );
            ''',
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql='''
            INSERT INTO dominial_lancamentopessoa (lancamento_id, pessoa_id, tipo)
            SELECT id, adquirente_id, 'adquirente'
            FROM dominial_lancamento
            WHERE adquirente_id IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM dominial_lancamentopessoa
                WHERE lancamento_id = dominial_lancamento.id
                  AND tipo = 'adquirente'
              );
            ''',
            reverse_sql=migrations.RunSQL.noop,
        ),

        # Step 2: Remove legacy columns
        migrations.RemoveField(
            model_name='lancamento',
            name='transmitente',
        ),
        migrations.RemoveField(
            model_name='lancamento',
            name='adquirente',
        ),
        migrations.RemoveField(
            model_name='lancamento',
            name='cartorio_transacao',
        ),
    ]
```

---

## Rollback Strategy

### Before Migration

1. **Full backup** of PostgreSQL database
2. **Export** critical tables to CSV
3. **Document** row counts for verification

```bash
# PostgreSQL backup
pg_dump cadeia_dominial > backup_before_migration.sql

# Row count documentation
psql cadeia_dominial -c "
SELECT table_name,
       (xpath('/row/cnt/text()', xml_count))[1]::text::int as row_count
FROM (
  SELECT table_name,
         query_to_xml(format('SELECT COUNT(*) as cnt FROM %I.%I',
                            table_schema, table_name), false, true, '') as xml_count
  FROM information_schema.tables
  WHERE table_schema = 'public' AND table_name LIKE 'dominial_%'
) t;
" > row_counts_before.txt
```

### Rollback Procedure

```bash
# If migration fails, restore from backup
psql cadeia_dominial < backup_before_migration.sql
```

### Verification Checklist

- [ ] All row counts match (with expected adjustments)
- [ ] Application test suite passes
- [ ] Key queries return correct results
- [ ] No orphaned records
- [ ] Foreign key integrity maintained

---

## Summary of Benefits

### Complexity Reduction

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Tables | 19 | 11 | -42% |
| Foreign Keys | ~35 | ~20 | -43% |
| Lookup Tables | 6 | 2 | -67% |
| Legacy Fields | 3 | 0 | -100% |

### SQLite Benefits

1. **Simpler deployment** - single file database
2. **No server required** - embedded database
3. **Easier backups** - copy single file
4. **Lower resource usage** - no connection pooling needed
5. **Better for read-heavy workloads** - which this application appears to be

### SQLite Limitations to Consider

1. **Single writer** - concurrent writes queue up
2. **No stored procedures** - move logic to application
3. **Limited ALTER TABLE** - some changes require table recreation
4. **Size limit** - practical limit ~1TB (unlikely to hit)

---

## Appendix: Data Volume Analysis

Run this query to understand current data volumes:

```sql
-- Get row counts and sizes for all dominial tables
SELECT
    t.table_name,
    pg_size_pretty(pg_total_relation_size('public.' || t.table_name)) as total_size,
    (xpath('/row/cnt/text()',
        query_to_xml(format('SELECT COUNT(*) as cnt FROM %I.%I',
                           'public', t.table_name), false, true, ''))
    )[1]::text::int as row_count
FROM information_schema.tables t
WHERE t.table_schema = 'public'
  AND t.table_name LIKE 'dominial_%'
ORDER BY pg_total_relation_size('public.' || t.table_name) DESC;
```

Alternative simpler query (requires running for each table):

```sql
-- Quick count of key tables
SELECT 'pessoas' as table_name, COUNT(*) as rows FROM dominial_pessoas
UNION ALL SELECT 'imovel', COUNT(*) FROM dominial_imovel
UNION ALL SELECT 'documento', COUNT(*) FROM dominial_documento
UNION ALL SELECT 'lancamento', COUNT(*) FROM dominial_lancamento
UNION ALL SELECT 'lancamentopessoa', COUNT(*) FROM dominial_lancamentopessoa
UNION ALL SELECT 'origemfimcadeia', COUNT(*) FROM dominial_origemfimcadeia
UNION ALL SELECT 'alteracoes', COUNT(*) FROM dominial_alteracoes;
```

**Important pre-migration checks:**

```sql
-- Check for multi-origin cases (blocks simple inline migration)
SELECT COUNT(*) as multi_origin_cases
FROM dominial_origemfimcadeia
WHERE indice_origem > 0;

-- Check for data in legacy fields (must migrate before dropping)
SELECT
    COUNT(*) FILTER (WHERE transmitente_id IS NOT NULL) as legacy_transmitente,
    COUNT(*) FILTER (WHERE adquirente_id IS NOT NULL) as legacy_adquirente,
    COUNT(*) FILTER (WHERE cartorio_transacao_id IS NOT NULL) as legacy_cartorio_transacao
FROM dominial_lancamento;
```

This helps prioritize which tables to focus optimization efforts on and validates migration readiness.
