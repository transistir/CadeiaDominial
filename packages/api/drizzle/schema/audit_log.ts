/**
 * AuditLog (operation log) Schema
 *
 * Q9=C: every mutation (CREATE, EDIT, SOFT_DELETE, RESTORE, MOVE, ANNOTATE,
 * EXPORT) creates an `audit_log` row. The `operation_id` UUID groups
 * all events from a single atomic user action (e.g. one MOVE dialog
 * confirmation produces one `audit_log` row + N
 * `lancamento_move_event` rows, all sharing the same `operation_id`).
 *
 * `payload_json` is a TEXT snapshot of the pre-action state. Stored as
 * JSON text (no encryption per Q4=A — v2 has no PII anyway).
 *
 * D3: `actor_id` is a USER (researcher), not a PESSOA. Researchers
 * are the system actors; pessoa is the cartório domain entity.
 *
 * NO soft-delete on audit_log: per Q2 the table is in the
 * "no `deleted_at`" exception list (append-only immutable log).
 * LGPD purge of a researcher's identity is handled by SET NULL on
 * `actor_id`, not by deleting the log row.
 *
 * `action` enum: 'CREATE' | 'EDIT' | 'SOFT_DELETE' | 'RESTORE' | 'MOVE' |
 * 'ANNOTATE' | 'EXPORT'. CHECK in migration.
 */

import { sql } from "drizzle-orm";
import { integer, sqliteTable, text } from "drizzle-orm/sqlite-core";
import { user } from "./user";

export const auditLog = sqliteTable("audit_log", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  /** UUID v4 generated in app layer. Groups all events of one operation. */
  operationId: text("operation_id").notNull(),
  /** CHECK (action IN ('CREATE','EDIT','SOFT_DELETE','RESTORE','MOVE','ANNOTATE','EXPORT')) — migration. */
  action: text("action", {
    enum: [
      "CREATE",
      "EDIT",
      "SOFT_DELETE",
      "RESTORE",
      "MOVE",
      "ANNOTATE",
      "EXPORT",
    ],
  }).notNull(),
  /** e.g. 'imovel' | 'documento' | 'lancamento' | 'anotacao' | 'mover' */
  entityType: text("entity_type").notNull(),
  entityId: integer("entity_id").notNull(),
  /** JSON text snapshot of pre-action state. */
  payloadJson: text("payload_json"),
  createdAt: text("created_at")
    .notNull()
    .default(sql`(current_timestamp)`),
  /** D3: USER (researcher), not pessoa. SET NULL on user LGPD-anonymization. */
  actorId: integer("actor_id").references(() => user.id, {
    onDelete: "set null",
  }),
});

// Type exports
export type AuditLog = typeof auditLog.$inferSelect;
export type NewAuditLog = typeof auditLog.$inferInsert;
