/**
 * CRI (Cartório de Registro de Imóveis) Schema
 *
 * Q11b: CRI is a separate entity. `documento.cri_id` and `imovel.cri_id` are
 * direct FKs (no junction table). `cartorio_transmissao` on lancamento is
 * FREE-FORM TEXT (`cartorio_transmissao_nome`), not an FK.
 *
 * D1: UNIQUE (cns_codigo) WHERE cns_codigo IS NOT NULL AND deleted_at IS NULL
 * is declared as a partial UNIQUE index in the migration (T1 in decisions).
 *
 * Q2: Soft-delete via `deleted_at`. Duplicate `nome` is allowed (e.g. a city
 * can have two "1º Cartório de Registro de Imóveis").
 *
 * T-100: `tipo` field re-added for parity with Django `Cartorios.tipo`.
 * CHECK (tipo IN ('CRI','OUTRO')), DEFAULT 'CRI'. Round-3 had struck
 * `cri.tipo_cartorio` (broader values CRI/NOTAS/CIVIL/TRANSMISSAO/OUTRO) as
 * out-of-scope; T-100 re-introduces a minimal subset because the `cri`
 * entity is specifically a cartório de registro de imóveis, not a generic
 * cartório. See T-100 addendum in `SCHEMA_DECISOES_PENDENTES.md`.
 *
 * T3 (SQLite/D1): booleans as INTEGER 0/1 with CHECK; dates as TEXT ISO8601.
 * UF is checked in app layer; v2 has 27 federative units.
 *
 * NOTE on DB-level constraints: `*.sql` migrations are git-ignored by
 * project policy. The DB-level CHECK for `tipo` is declared via Drizzle's
 * `check()` API in this file and emitted into the generated migration by
 * `drizzle-kit generate` (run on-the-fly in CI; not committed to git).
 * The `uf` column remains a plain `text` (v2 has 27 federative units;
 * validation lives in the app layer, not the DB).
 */

import { sql } from "drizzle-orm";
import { integer, sqliteTable, text, uniqueIndex, check } from "drizzle-orm/sqlite-core";

export const cri = sqliteTable(
  "cri",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    nome: text("nome").notNull(),
    /** Cadastro Nacional de Serventia (TBD exact format; nullable until mapped). */
    cnsCodigo: text("cns_codigo"),
    cidade: text("cidade"),
    /** 27 federative units (BR). Validated in the app layer; no DB-level CHECK. */
    uf: text("uf"),
    endereco: text("endereco"),
    /**
     * T-100: parity with Django `Cartorios.tipo`. Minimal subset
     * ('CRI' | 'OUTRO') — see T-100 addendum in `SCHEMA_DECISOES_PENDENTES.md`.
     * DB-level CHECK emitted by `drizzle-kit generate` from the `check()`
     * below (migrations are git-ignored; see JSDoc header).
     */
    tipo: text("tipo", { enum: ["CRI", "OUTRO"] })
      .notNull()
      .default("CRI"),
    /** ISO8601 UTC TEXT, generated in app layer (Node `new Date().toISOString()`). */
    createdAt: text("created_at")
      .notNull(),
    updatedAt: text("updated_at")
      .notNull()
      .$onUpdate(() => new Date().toISOString()),
    /** Q2=B: soft-delete. NULL = active. ISO8601 UTC TEXT. */
    deletedAt: text("deleted_at"),
  },
  (table) => ({
    /**
     * D1/T1: partial UNIQUE on cns_codigo — only enforced when both
     * cns_codigo is set AND the row is not soft-deleted. Multiple CRIs can
     * share a nome; CNS code is the canonical identifier when present.
     *
     * Drizzle 0.45 supports `uniqueIndex(...).where(...)` for partial UNIQUE.
     */
    cnsCodigoActiveUnique: uniqueIndex("uq_cri_cns_codigo_active")
      .on(table.cnsCodigo)
      .where(sql`${table.cnsCodigo} IS NOT NULL AND ${table.deletedAt} IS NULL`),
    /**
     * T-100: DB-level CHECK for `tipo`. The Drizzle `enum: []` above is
     * TS-level only; this `check()` produces the actual SQL CHECK in the
     * generated migration (which is git-ignored by project policy).
     */
    tipoCheck: check(
      "cri_tipo_check",
      sql`${table.tipo} IN ('CRI', 'OUTRO')`
    ),
  })
);

// Type exports
export type Cri = typeof cri.$inferSelect;
export type NewCri = typeof cri.$inferInsert;
