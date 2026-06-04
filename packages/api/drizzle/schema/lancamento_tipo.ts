/**
 * LancamentoTipo (lookup table) Schema
 *
 * Lookup table for the 3 valid Lancamento types. No soft-delete (append-only
 * reference data). CHECK constraint on `tipo` is enforced in migration:
 *   CHECK (tipo IN ('inicio_matricula','registro','averbacao'))
 *
 * F3 (round 2): F3 added `lancamento_tipo ||--o{ lancamento : "classifica
 * (tipo_id, F3)"` to the ERD — this is the FK for that relationship.
 *
 * `requer_*` flags drive UI form rendering (which fields are required
 * for a given Lancamento type).
 */

import { integer, sqliteTable, text } from "drizzle-orm/sqlite-core";

export const lancamentoTipo = sqliteTable("lancamento_tipo", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  /**
   * CHECK (tipo IN ('inicio_matricula','registro','averbacao')) — enforced
   * in the generated migration. The `text({ enum: [...] })` Drizzle type
   * is TS-only; SQLite-level CHECK is added via Drizzle Kit custom SQL.
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
});

// Type exports
export type LancamentoTipo = typeof lancamentoTipo.$inferSelect;
export type NewLancamentoTipo = typeof lancamentoTipo.$inferInsert;
