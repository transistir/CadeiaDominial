/**
 * LancamentoTipo (lookup table) Schema
 *
 * Lookup table for the 3 valid Lancamento types. No soft-delete (append-only
 * reference data). DB-level CHECK on `tipo` is declared via Drizzle's
 * `check()` API in this file and emitted into the generated migration by
 * `drizzle-kit generate` (run on-the-fly in CI; the migration `.sql` is
 * git-ignored by project policy).
 *
 * F3 (round 2): F3 added `lancamento_tipo ||--o{ lancamento : "classifica
 * (tipo_id, F3)"` to the ERD — this is the FK for that relationship.
 *
 * `requer_*` flags drive UI form rendering (which fields are required
 * for a given Lancamento type). All 10 booleans are 0/1 with a composite
 * DB-level CHECK (T3 spec).
 */

import { sql } from "drizzle-orm";
import { integer, sqliteTable, text, check } from "drizzle-orm/sqlite-core";

/**
 * Composite CHECK: all 10 `requer_*` booleans are 0 or 1.
 * The composite form keeps the schema compact; DB-level enforcement matches
 * the T3 spec (INTEGER 0/1 with CHECK).
 */
const REQUER_BOOLEANS = sql`requer_detalhes IN (0, 1)
  AND requer_transmissao IN (0, 1)
  AND requer_cartorio_origem IN (0, 1)
  AND requer_data_origem IN (0, 1)
  AND requer_descricao IN (0, 1)
  AND requer_folha_origem IN (0, 1)
  AND requer_forma IN (0, 1)
  AND requer_livro_origem IN (0, 1)
  AND requer_observacao IN (0, 1)
  AND requer_titulo IN (0, 1)`;

export const lancamentoTipo = sqliteTable(
  "lancamento_tipo",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    /**
     * DB-level CHECK (emitted by `drizzle-kit generate` from the `check()`
     * below) — Drizzle `text({ enum: [...] })` is TS-only. The list of
     * Lancamento types is FIXED in v2; not domain-extensible.
     */
    tipo: text("tipo", {
      enum: ["inicio_matricula", "registro", "averbacao"],
    }).notNull(),
    /** Human-readable label for the UI. */
    nome: text("nome").notNull(),
    /** 0/1 boolean flags driving UI form rendering. */
    requerDetalhes: integer("requer_detalhes", { mode: "boolean" })
      .notNull()
      .default(false),
    requerTransmissao: integer("requer_transmissao", { mode: "boolean" })
      .notNull()
      .default(false),
    requerCartorioOrigem: integer("requer_cartorio_origem", { mode: "boolean" })
      .notNull()
      .default(false),
    requerDataOrigem: integer("requer_data_origem", { mode: "boolean" })
      .notNull()
      .default(false),
    requerDescricao: integer("requer_descricao", { mode: "boolean" })
      .notNull()
      .default(false),
    requerFolhaOrigem: integer("requer_folha_origem", { mode: "boolean" })
      .notNull()
      .default(false),
    requerForma: integer("requer_forma", { mode: "boolean" })
      .notNull()
      .default(false),
    requerLivroOrigem: integer("requer_livro_origem", { mode: "boolean" })
      .notNull()
      .default(false),
    requerObservacao: integer("requer_observacao", { mode: "boolean" })
      .notNull()
      .default(false),
    requerTitulo: integer("requer_titulo", { mode: "boolean" })
      .notNull()
      .default(false),
  },
  (table) => ({
    tipoCheck: check(
      "lancamento_tipo_tipo_check",
      sql`${table.tipo} IN ('inicio_matricula', 'registro', 'averbacao')`
    ),
    booleanCheck: check("lancamento_tipo_boolean_check", REQUER_BOOLEANS),
  })
);

// Type exports
export type LancamentoTipo = typeof lancamentoTipo.$inferSelect;
export type NewLancamentoTipo = typeof lancamentoTipo.$inferInsert;
