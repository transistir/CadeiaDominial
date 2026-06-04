/**
 * Documento (matricula / transcricao) Schema
 *
 * Q11b=C: `documento.cri_id` is a direct FK, NOT a junction. Each Documento
 * has exactly one CRI.
 *
 * Q11b=UNIQUE: `UNIQUE (cri_id, tipo, numero)` — cartório + tipo + numero
 * is the natural key. Two CRIs can have the same numero for different
 * documents; the same CRI can have a matricula and a transcricao with
 * the same numero (they are distinct documents).
 *
 * Q10: `numero` is normalized (digits only) for indexing. `numero_raw` is
 * the verbatim original value (preserved for evidence of divergence
 * between certidões — grilagem research relies on this fidelity).
 *
 * Q2=B: soft-delete. Q15=D4: deleting a shared Documento is admin-only.
 * Default user action when the Documento is in multiple chains is
 * "unlink from this chain" (set `imovel_documento.deleted_at`), NOT
 * soft-delete the Documento itself.
 *
 * Q9=C: `create_operation_id` and `delete_operation_id` reference
 * `audit_log.id` for provenance.
 *
 * The FK to `cri` is RESTRICT — a CRI cannot be removed while Documentos
 * reference it. Admin has hard-delete.
 *
 * `outorgante_nome`, `outorgado_nome`, `endereco` are FTS5-searchable
 * (Q10=A). FTS5 sync triggers are a separate task; T-101 does not
 * create virtual FTS5 tables.
 */

import { sql } from "drizzle-orm";
import { integer, sqliteTable, text, uniqueIndex } from "drizzle-orm/sqlite-core";
import { cri } from "./cri";

export const documento = sqliteTable(
  "documento",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    /**
     * CHECK (tipo IN ('matricula','transcricao')) — enforced in migration.
     * Drizzle `enum` is TS-only.
     */
    tipo: text("tipo", {
      enum: ["matricula", "transcricao"],
    }).notNull(),
    /**
     * Q10: normalized (digits only) for indexing. Search & sort by this.
     */
    numero: text("numero").notNull(),
    /**
     * Q10: verbatim original value, preserved as evidence of cartório
     * divergence. NOT indexed; NOT used for lookup.
     */
    numeroRaw: text("numero_raw"),
    /**
     * Partial date per T3 (cartório: 'YYYY-MM-DD' | 'YYYY-MM' | 'YYYY').
     */
    data: text("data"),
    livro: text("livro"),
    folha: text("folha"),
    dataCadastro: text("data_cadastro"),
    /**
     * Q11b=C: direct FK to CRI, no junction. RESTRICT (admin-only hard delete).
     */
    criId: integer("cri_id")
      .notNull()
      .references(() => cri.id, { onDelete: "restrict" }),
    /** FTS5-searchable (Q10). */
    outorganteNome: text("outorgante_nome"),
    /** FTS5-searchable (Q10). */
    outorgadoNome: text("outorgado_nome"),
    /** FTS5-searchable (Q10). */
    endereco: text("endereco"),
    createdAt: text("created_at")
      .notNull()
      .default(sql`(current_timestamp)`),
    /** Q2=B: soft-delete. NULL = active. */
    deletedAt: text("deleted_at"),
    /** Q9+C: provenance of the soft-delete. SET NULL if audit purged. */
    deleteOperationId: integer("delete_operation_id"),
    /** Q9+C: provenance of the creation. */
    createOperationId: integer("create_operation_id"),
  },
  (table) => ({
    /**
     * Q11b=C: cartório + tipo + numero is the natural key.
     * (Drizzle `unique()` on the table column-options may be simpler; the
     * explicit index name is friendlier in migration diffs.)
     */
    criTipoNumeroUnique: uniqueIndex("uq_documento_cri_tipo_numero").on(
      table.criId,
      table.tipo,
      table.numero
    ),
    /** CHECK constraints for booleans/enums. */
    // tipo is constrained by the Drizzle `enum` option; the DB-level CHECK
    // is added via Drizzle Kit custom SQL in the migration.
  })
);

// Type exports
export type Documento = typeof documento.$inferSelect;
export type NewDocumento = typeof documento.$inferInsert;
