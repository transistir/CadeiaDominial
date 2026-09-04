# Drizzle ORM Schema - SQLite Version

This directory contains the SQLite-compatible Drizzle ORM schema for the Sistema de Cadeia Dominial project. It mirrors the PostgreSQL schema in `/drizzle/` but with SQLite-specific adaptations.

## When to Use This Schema

- **Local development** with SQLite (Django's default dev database)
- **Testing environments** where PostgreSQL isn't available
- **Lightweight deployments** that don't require PostgreSQL features
- **Embedded applications** or single-user scenarios

For production with concurrent users, prefer the PostgreSQL schema in `/drizzle/`.

## Key Differences from PostgreSQL Version

| Feature | PostgreSQL (`/drizzle/`) | SQLite (`/drizzle-sqlite/`) |
|---------|--------------------------|------------------------------|
| **Primary keys** | `serial('id')` | `integer('id').primaryKey({ autoIncrement: true })` |
| **Strings** | `varchar('col', { length: N })` | `text('col')` (no length enforcement) |
| **Decimals** | `decimal('col', { precision, scale })` | `real('col')` (floating point) |
| **Booleans** | `boolean('col')` | `integer('col', { mode: 'boolean' })` |
| **Timestamps** | `timestamp('col')` | `text('col')` (ISO 8601 strings) |
| **Dates** | `date('col')` | `text('col')` (YYYY-MM-DD strings) |
| **Enums** | `pgEnum('name', [...])` | N/A (use text with validation) |
| **Default now** | `defaultNow()` | `default(sql\`(datetime('now'))\`)` |
| **Indexes** | `index().on(...)` | `index('name').on(...)` |

## Installation

```bash
# Install dependencies
npm install drizzle-orm better-sqlite3
npm install -D drizzle-kit @types/better-sqlite3

# Or with pnpm
pnpm add drizzle-orm better-sqlite3
pnpm add -D drizzle-kit @types/better-sqlite3
```

## Usage

### Basic Queries

```typescript
import { db } from './drizzle-sqlite/db';
import { pessoas, imovel, tis } from './drizzle-sqlite/schema';
import { eq } from 'drizzle-orm';

// Select all people
const allPessoas = db.select().from(pessoas).all();

// Find property by matricula
const property = db
  .select()
  .from(imovel)
  .where(eq(imovel.matricula, '12345'))
  .get();

// Insert a new person
const newPessoa = db
  .insert(pessoas)
  .values({
    nome: 'João Silva',
    cpf: '12345678901',
  })
  .returning()
  .get();
```

### Relational Queries

```typescript
// Get properties with related data
const propertiesWithDetails = db.query.imovel.findMany({
  with: {
    terraIndigena: true,
    proprietario: true,
    cartorio: true,
    documentos: {
      with: {
        lancamentos: true,
      },
    },
  },
});

// Get a single TI with all properties
const tiWithProperties = db.query.tis.findFirst({
  where: eq(tis.codigo, 'TI-001'),
  with: {
    imoveis: {
      with: {
        proprietario: true,
      },
    },
  },
});
```

## SQLite-Specific Considerations

### 1. Foreign Keys

SQLite has foreign keys disabled by default. The `db.ts` enables them via:

```sql
PRAGMA foreign_keys = ON;
```

This is already configured in the database client.

### 2. Date/Time Handling

SQLite stores dates as text. Use ISO 8601 format:

```typescript
// Inserting dates
db.insert(documento).values({
  data: '2024-01-15',              // Date as YYYY-MM-DD
  dataCadastro: new Date().toISOString().split('T')[0], // Today
});

// Querying dates
const recentDocs = db
  .select()
  .from(documento)
  .where(sql`data > date('now', '-30 days')`)
  .all();
```

### 3. Decimal Precision

SQLite uses `real` (floating point) instead of true decimals. For financial calculations requiring exact precision, consider:

```typescript
// Store as integer cents
valorTransacao: integer('valor_transacao_cents'),

// Or store as text and parse
valorTransacao: text('valor_transacao'),
```

### 4. Boolean Values

SQLite stores booleans as integers (0/1). Drizzle handles this automatically with `{ mode: 'boolean' }`:

```typescript
// In schema
arquivado: integer('arquivado', { mode: 'boolean' }).notNull().default(false),

// In queries - works with true/false
db.select().from(imovel).where(eq(imovel.arquivado, false));
```

### 5. Concurrent Access

SQLite has limited concurrent write support. WAL mode (enabled in `db.ts`) helps:

```sql
PRAGMA journal_mode = WAL;
```

For high-concurrency scenarios, use the PostgreSQL schema instead.

## Migrations

### Generate migrations from schema changes:

```bash
npx drizzle-kit generate --config=./drizzle-sqlite/drizzle.config.ts
```

### Push schema directly (development only):

```bash
npx drizzle-kit push --config=./drizzle-sqlite/drizzle.config.ts
```

### Open Drizzle Studio:

```bash
npx drizzle-kit studio --config=./drizzle-sqlite/drizzle.config.ts
```

## Django Compatibility

This schema is designed to work alongside Django's ORM. Both can read/write to the same SQLite database (`db.sqlite3`).

**Important:** When using both ORMs:
- Let Django manage migrations (it owns the schema)
- Use Drizzle for TypeScript/Node.js code that needs database access
- Avoid running Drizzle migrations against Django-managed databases

## File Structure

```
drizzle-sqlite/
├── db.ts                 # Database client (better-sqlite3)
├── drizzle.config.ts     # Drizzle Kit configuration
├── README.md             # This file
└── schema/
    ├── index.ts          # Exports all schemas
    ├── tis.ts            # Indigenous lands
    ├── pessoas.ts        # People/persons
    ├── cartorios.ts      # Registry offices
    ├── imovel.ts         # Properties
    ├── documentos.ts     # Documents
    ├── lancamentos.ts    # Recordings/transactions
    ├── alteracoes.ts     # Amendments
    └── relations.ts      # Drizzle relations
```

## See Also

- [PostgreSQL Schema](/drizzle/) - Production-ready PostgreSQL version
- [Database Schema Documentation](/docs/DATABASE_SCHEMA.md) - Full schema reference
- [Drizzle ORM Docs](https://orm.drizzle.team/) - Official documentation
