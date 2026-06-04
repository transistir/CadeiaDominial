/**
 * AnotacaoVersao (researcher annotation version on a chain-membership) Schema
 *
 * Q9=C: annotations on `imovel_documento` (chain-membership) are versioned.
 * Each edit creates a new row with `versao = previous + 1`. The latest
 * `is_current = 1` row is the active annotation; older rows (`is_current = 0`)
 * are kept in history.
 *
 * F2 (Codex round 2 BLOCKER): `deleted_at` was added. The semantics:
 *  - `is_current = 0` — version is in history, not active. Annotation
 *    still exists. UI hides it.
 *  - `deletedAt` (NOT NULL) — the ENTIRE annotation (all versions) was
 *    soft-deleted. UI hides everything.
 *
 * D3 (round 2 fix F1): `autor_original_id` and `created_by_id` both
 * reference `user` (researcher), not `pessoa` (cartório entity). In
 * team research, the original author and the editor of a specific
 * version can differ — that's why we have both.
 *
 * FK actions:
 *  - `imovel_documento_id` → CASCADE (annotation follows the junction).
 *  - `autor_original_id` → RESTRICT (immutable history — original author
 *    cannot be anonymized away; the version loses its provenance).
 *  - `created_by_id` → SET NULL (editor can be removed; version remains
 *    with original-author attribution).
 *  - `operation_id` (audit_log) → SET NULL (audit can be purged; annotation
 *    preserved).
 *
 * T1: UNIQUE (imovel_documento_id) WHERE is_current = 1 AND deleted_at IS
 * NULL — at most one current annotation per chain-membership.
 */

import { sql } from "drizzle-orm";
import {
  integer,
  sqliteTable,
  text,
  uniqueIndex,
  check,
} from "drizzle-orm/sqlite-core";
import { imovelDocumento } from "./imovel_documento";
import { user } from "./user";
import { auditLog } from "./audit_log";

export const anotacaoVersao = sqliteTable(
  "anotacao_versao",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    /** CASCADE — annotation follows the junction. */
    imovelDocumentoId: integer("imovel_documento_id")
      .notNull()
      .references(() => imovelDocumento.id, { onDelete: "cascade" }),
    /**
     * F1/D3: original researcher (immutable). RESTRICT.
     */
    autorOriginalId: integer("autor_original_id")
      .notNull()
      .references(() => user.id, { onDelete: "restrict" }),
    /** 1, 2, 3... monotonic per imovel_documento. */
    versao: integer("versao").notNull(),
    /** Annotation text. FTS5-searchable in a later task. */
    texto: text("texto").notNull(),
    /**
     * F2: 1 = current version (shown in UI), 0 = historical (hidden but
     * retained). NOT to be confused with `deletedAt` (which deletes the
     * ENTIRE annotation across all versions).
     */
    isCurrent: integer("is_current", { mode: "boolean" })
      .notNull()
      .default(false),
    createdAt: text("created_at")
      .notNull()
      .default(sql`(current_timestamp)`),
    /** F2: soft-delete the entire annotation. */
    deletedAt: text("deleted_at"),
    /** D3: editor of THIS version (can differ from autor_original). SET NULL. */
    createdById: integer("created_by_id").references(() => user.id, {
      onDelete: "set null",
    }),
    /** Q9+C: provenance (audit log id). SET NULL if audit purged. */
    operationId: integer("operation_id").references(() => auditLog.id, {
      onDelete: "set null",
    }),
  },
  (table) => ({
    /**
     * T1: at most one current annotation per chain-membership.
     */
    imovelDocumentoCurrentActiveUnique: uniqueIndex(
      "uq_anotacao_versao_imovel_documento_current"
    )
      .on(table.imovelDocumentoId)
      .where(
        sql`${table.isCurrent} = 1 AND ${table.deletedAt} IS NULL`
      ),
    isCurrentCheck: check(
      "anotacao_versao_is_current_check",
      sql`${table.isCurrent} IN (0, 1)`
    ),
    versaoPositivo: check(
      "anotacao_versao_versao_positivo",
      sql`${table.versao} > 0`
    ),
  })
);

// Type exports
export type AnotacaoVersao = typeof anotacaoVersao.$inferSelect;
export type NewAnotacaoVersao = typeof anotacaoVersao.$inferInsert;
