/**
 * LancamentoMoveEvent (MOVE cross-chain event log) Schema
 *
 * Q14=B: APPEND-ONLY. The MOVE operation does NOT mutate the Lancamento.
 * It records a `lancamento_move_event` row that future queries consult
 * (via the `v_lancamento_current_location` view in `views.ts`).
 *
 * NO `updated_at`, NO `deleted_at` — append-only by design.
 *
 * FK actions:
 *  - `lancamento_id` → RESTRICT (Q14=B: Lancamento is immutable, never
 *    hard-deleted in normal flow).
 *  - `from_documento_id` → SET NULL (originating Documento can be removed;
 *    the move event preserves its history).
 *  - `to_documento_id` → SET NULL (destination Documento can be removed;
 *    ditto).
 *  - `moved_by_id` (user) → SET NULL (researcher can be LGPD-anonymized;
 *    move event preserved).
 *  - `audit_log_id` → SET NULL (audit can be purged; event preserved).
 *
 * Q14 write-time invariante (in app, not DB): before creating this row,
 * validate that `from_documento_id` matches the current location per
 * `v_lancamento_current_location` for that Lancamento. See
 * `docs/db/SCHEMA_DECISOES_PENDENTES.md` Q14 implementation.
 *
 * `reason` is REQUIRED (Q12=D: dialog requires the user to type a
 * reason for the MOVE). CHECK (length(reason) > 0) in migration.
 */

import { sql } from "drizzle-orm";
import { integer, sqliteTable, text, check, index } from "drizzle-orm/sqlite-core";
import { lancamento } from "./lancamento";
import { documento } from "./documento";
import { user } from "./user";

export const lancamentoMoveEvent = sqliteTable(
  "lancamento_move_event",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    /** RESTRICT — Lancamento is immutable. */
    lancamentoId: integer("lancamento_id")
      .notNull()
      .references(() => lancamento.id, { onDelete: "restrict" }),
    fromDocumentoId: integer("from_documento_id").references(() => documento.id, {
      onDelete: "set null",
    }),
    toDocumentoId: integer("to_documento_id").references(() => documento.id, {
      onDelete: "set null",
    }),
    /** Q12=D: required. CHECK (length(reason) > 0) in migration. */
    reason: text("reason").notNull(),
    movedById: integer("moved_by_id").references(() => user.id, {
      onDelete: "set null",
    }),
    /** ISO8601 UTC TEXT, generated in app layer. */
    movedAt: text("moved_at").notNull(),
    /** FK to audit_log row with action='MOVE' (Q9+C). */
    auditLogId: integer("audit_log_id"),
  },
  (table) => ({
    /**
     * Index for the v_lancamento_current_location view: lookup by
     * (lancamento_id, moved_at DESC, id DESC) to find the latest move.
     */
    lancamentoMovedAtIdIdx: index("idx_lancamento_move_event_lancamento_moved_at").on(
      table.lancamentoId,
      table.movedAt,
      table.id
    ),
    reasonNaoVazio: check(
      "lancamento_move_event_reason_nao_vazio",
      sql`length(${table.reason}) > 0`
    ),
  })
);

// Type exports
export type LancamentoMoveEvent = typeof lancamentoMoveEvent.$inferSelect;
export type NewLancamentoMoveEvent = typeof lancamentoMoveEvent.$inferInsert;
