# Drizzle ORM Schema

This directory contains the Drizzle ORM schema definition for the Sistema de Cadeia Dominial database.

## Overview

The schema mirrors the Django models defined in `dominial/models/` and can be used for TypeScript/JavaScript applications that need to interact with the same PostgreSQL database.

## Structure

```
drizzle/
├── schema/
│   ├── index.ts          # Main export file
│   ├── tis.ts            # Indigenous lands tables
│   ├── pessoas.ts        # People/persons table
│   ├── cartorios.ts      # Registry offices tables
│   ├── imovel.ts         # Properties tables
│   ├── documentos.ts     # Documents tables
│   ├── lancamentos.ts    # Recordings/transactions tables
│   ├── alteracoes.ts     # Amendments tables
│   └── relations.ts      # Table relations definitions
├── db.ts                 # Database client
├── drizzle.config.ts     # Drizzle Kit configuration
└── README.md             # This file
```

## Installation

```bash
# Install dependencies
npm install drizzle-orm pg
npm install -D drizzle-kit @types/pg
```

## Environment Variables

Set the following environment variables for database connection:

```bash
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your_password
DB_NAME=cadeia_dominial
```

## Usage

### Basic Queries

```typescript
import { db } from './drizzle/db';
import { pessoas, imovel, documento } from './drizzle/schema';
import { eq, and } from 'drizzle-orm';

// Select all pessoas
const allPessoas = await db.select().from(pessoas);

// Select with filter
const pessoa = await db
  .select()
  .from(pessoas)
  .where(eq(pessoas.cpf, '12345678901'));

// Insert
const newPessoa = await db
  .insert(pessoas)
  .values({
    nome: 'João Silva',
    cpf: '12345678901',
  })
  .returning();
```

### Relational Queries

```typescript
import { db } from './drizzle/db';

// Get imoveis with related data
const imoveisWithRelations = await db.query.imovel.findMany({
  with: {
    proprietario: true,
    cartorio: true,
    terraIndigena: true,
    documentos: {
      with: {
        lancamentos: true,
      },
    },
  },
});

// Get documento chain
const documentoWithChain = await db.query.documento.findFirst({
  where: (doc, { eq }) => eq(doc.id, 1),
  with: {
    lancamentos: {
      with: {
        documentoOrigem: true,
        pessoas: {
          with: {
            pessoa: true,
          },
        },
      },
    },
  },
});
```

### Transactions

```typescript
import { db } from './drizzle/db';
import { pessoas, imovel } from './drizzle/schema';

await db.transaction(async (tx) => {
  const [pessoa] = await tx
    .insert(pessoas)
    .values({ nome: 'Maria Santos' })
    .returning();

  await tx.insert(imovel).values({
    nome: 'Fazenda Exemplo',
    proprietarioId: pessoa.id,
    // ... other fields
  });
});
```

## Migrations

### Generate Migrations

```bash
npx drizzle-kit generate
```

### Apply Migrations

```bash
npx drizzle-kit migrate
```

### Introspect Existing Database

If you need to update the schema from the existing Django-managed database:

```bash
npx drizzle-kit introspect
```

## Notes

- This schema is designed to be compatible with the existing Django models
- Table names follow Django's naming convention (`dominial_tablename`)
- Foreign key constraints match Django's `on_delete` behavior
- The schema uses PostgreSQL-specific features

## Schema Documentation

For detailed documentation of all tables, columns, and relationships, see [DATABASE_SCHEMA.md](../docs/DATABASE_SCHEMA.md).
