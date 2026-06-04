/**
 * ImovelDocumento (chain-membership junction) Schema
 *
 * Q13=B: N:N junction for chain membership. `documento.imovel_id` and
 * `documento.is_documento_atual` were REMOVED in v2 — chain membership
 * lives here, with `is_documento_atual` per (Imovel, Documento) pair.
 *
 * T1: UNIQUE (imovel_id, documento_id) WHERE deleted_at IS NULL — at most
 * one active chain-membership per (I, D) pair.
 *
 * Q15=D4: UNIQUE (imovel_id) WHERE is_documento_atual = 1 AND deleted_at
 * IS NULL — at most one "current" Documento per Imovel. This is enforced
 * via a partial UNIQUE index.
 *
 * Q9=C: `create_operation_id` and `delete_operation_id` track audit-log
 * provenance. SET NULL if the audit log is purged.
 *
 * Q7b=B: `imovel_id` ON DELETE CASCADE (Q7b=B: junction follows the Imovel
 * on soft-delete). `documento_id` is RESTRICT (Q15=D4: deleting a Documento
 * is admin-only and explicit — junction must NOT silently follow).
 *
 * The "deleted_at" is per chain-membership: soft-deleting this row means
 * the Documento is unlinked from this Imovel's chain (Q15=D4 default action:
 * "Desvincular desta cadeia"). The Documento itself is untouched.
 */

import { sql } from "drizzle-orm";
import { integer, sqliteTable, text, uniqueIndex, check } from "drizzle-orm/sqlite-core";
import { imovel } from "./imovel";
import { documento } from "./documento";
import { auditLog } from "./audit_log";

export const imovelDocumento = sqliteTable(
  "imovel_documento",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    imovelId: integer("imovel_id")
      .notNull()
      .references(() => imovel.id, { onDelete: "cascade" }),
    documentoId: integer("documento_id")
      .notNull()
      .references(() => documento.id, { onDelete: "restrict" }),
    /**
     * Q13=B: per-pair flag. Per-(Imovel, Documento) "is current" — NOT
     * a global flag on documento itself.
     */
    isDocumentoAtual: integer("is_documento_atual", { mode: "boolean" })
      .notNull()
      .default(false),
    createdAt: text("created_at")
      .notNull()
      .default(sql`(current_timestamp)`),
    /**
     * Q2=B: soft-delete per chain-membership. Soft-deleting this row
     * means "this Documento is unlinked from this Imovel's chain" (Q15=D4).
     * The Documento itself remains valid in other chains.
     */
    deletedAt: text("deleted_at"),
    /** Q9+C/Q8=A: provenance of the soft-delete (junction unlink). */
    deleteOperationId: integer("delete_operation_id").references(
      () => auditLog.id,
      { onDelete: "set null" }
    ),
    /** Q9+C: provenance of the chain-membership creation. */
    createOperationId: integer("create_operation_id").references(
      () => auditLog.id,
      { onDelete: "set null" }
    ),
  },
  (table) => ({
    /**
     * T1+Q13: at most one active (Imovel, Documento) pair per chain.
     */
    imovelDocumentoPairActiveUnique: uniqueIndex(
      "uq_imovel_documento_pair_active"
    )
      .on(table.imovelId, table.documentoId)
      .where(sql`${table.deletedAt} IS NULL`),
    /**
     * Q15=D4: at most one "current" Documento per Imovel.
     */
    imovelDocumentoAtualActiveUnique: uniqueIndex(
      "uq_imovel_documento_atual_active"
    )
      .on(table.imovelId)
      .where(
        sql`${table.isDocumentoAtual} = 1 AND ${table.deletedAt} IS NULL`
      ),
    isDocumentoAtualCheck: check(
      "imovel_documento_is_documento_atual_check",
      sql`${table.isDocumentoAtual} IN (0, 1)`
    ),
  })
);

// Type exports
export type ImovelDocumento = typeof imovelDocumento.$inferSelect;
export type NewImovelDocumento = typeof imovelDocumento.$inferInsert;
