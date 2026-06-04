/**
 * Origem (origin reference in a Lancamento) Schema
 *
 * Each Lancamento can have 0..N origens (Q3=B: 1:N). Origem is a verbatim
 * reference to a previous document — it has its own `cri_id`, `tipo`,
 * `numero`, `livro`, `folha`, `data` fields, copied from the cited
 * cartório record. This is the grilagem-research pattern: we keep the
 * verbatim citation even if we later link to a real Documento row.
 *
 * Q11b=A: `cri_id` IS the `cri_origem_id` (we don't need a separate column
 * on Lancamento).
 *
 * D2/Q10: `numero` (normalized, digits only) and `numero_raw` (verbatim
 * original) — divergence between certidões is evidence.
 *
 * R3-6 (Codex round 3 MUST-FIX): `lancamento_id` is ON DELETE RESTRICT.
 * Origem carries forensic evidence; cascading would destroy it. Hard-delete
 * of Lancamento is admin-only and explicit.
 *
 * `documento_id` is ON DELETE SET NULL: an Origem can be linked to a
 * Documento (when we have one in our system), but if that Documento is
 * removed the Origem remains as a verbatim citation.
 *
 * UNIQUE (lancamento_id, indice): per-Lancamento ordered list of origens.
 * Indice is 0-based and contiguous.
 *
 * Q2=B: soft-delete via `deleted_at` (NULL = active). The origens are
 * forensic evidence and rarely deleted, but the field is here for parity
 * with the rest of the Q2=B inventory (see legend soft-delete list).
 */

import { sql } from "drizzle-orm";
import { integer, sqliteTable, text, uniqueIndex, check } from "drizzle-orm/sqlite-core";
import { lancamento } from "./lancamento";
import { cri } from "./cri";
import { documento } from "./documento";

export const origem = sqliteTable(
  "origem",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    /** R3-6: RESTRICT — Origem carries forensic evidence. */
    lancamentoId: integer("lancamento_id")
      .notNull()
      .references(() => lancamento.id, { onDelete: "restrict" }),
    /** Q11b=A: `cri_id` IS the CRI of origin. */
    criId: integer("cri_id")
      .notNull()
      .references(() => cri.id, { onDelete: "restrict" }),
    /**
     * Optional FK to a Documento in our system. NULL when tipo =
     * 'fim_cadeia' (no document, end of chain). SET NULL on documento
     * delete — Origem remains as verbatim citation.
     */
    documentoId: integer("documento_id").references(() => documento.id, {
      onDelete: "set null",
    }),
    /** 0-based, contiguous per Lancamento. CHECK (indice >= 0). */
    indice: integer("indice").notNull(),
    /**
     * DB-level CHECK (emitted by `drizzle-kit generate` from the `check()`
     * below) — Drizzle `text({ enum: [...] })` is TS-only. The list of
     * Origem types is FIXED in v2.
     */
    tipo: text("tipo", {
      enum: ["matricula", "transcricao", "fim_cadeia"],
    }).notNull(),
    /** D2/Q10: normalized (digits only) for search. */
    numero: text("numero"),
    /** D2/Q10: verbatim original, preserved as evidence. */
    numeroRaw: text("numero_raw"),
    livro: text("livro"),
    folha: text("folha"),
    /** Partial date per T3. */
    data: text("data"),
    observacoes: text("observacoes"),
    createdAt: text("created_at")
      .notNull(),
    /** Q2=B: soft-delete. NULL = active. ISO8601 UTC TEXT. */
    deletedAt: text("deleted_at"),
  },
  (table) => ({
    /** UNIQUE (lancamento_id, indice) per ERD. */
    lancamentoIndiceUnique: uniqueIndex("uq_origem_lancamento_indice").on(
      table.lancamentoId,
      table.indice
    ),
    /** CHECK (indice >= 0). */
    indiceNaoNegativo: check(
      "origem_indice_nao_negativo",
      sql`${table.indice} >= 0`
    ),
    /**
     * DB-level CHECK (emitted by `drizzle-kit generate` from this `check()`).
     */
    tipoCheck: check(
      "origem_tipo_check",
      sql`${table.tipo} IN ('matricula', 'transcricao', 'fim_cadeia')`
    ),
  })
);

// Type exports
export type Origem = typeof origem.$inferSelect;
export type NewOrigem = typeof origem.$inferInsert;
