/**
 * User (researcher) Schema
 *
 * D3: `user` is a separate table from `pessoa`. Researchers are application
 * users (not cartório entities). FKs from `audit_log.actor_id`,
 * `lancamento_move_event.moved_by_id`, `anotacao_versao.autor_original_id`,
 * and `anotacao_versao.created_by_id` all reference this table.
 *
 * D3 (round 2 fix F1): `anotacao_versao.autor_original_id` is a user FK,
 * not a pessoa FK. Researchers create annotations; the "pessoa" in cartório
 * is a separate concept (domain entity, not a system actor).
 *
 * Q1+Q2: Soft-delete. LGPD allows researchers to request anonymization of
 * their own user record.
 *
 * NOTE: There is also a scaffolding `users` table in `schema.ts` (the
 * JWT-auth backbone for the API). The v2 `user` table is the domain
 * researcher entity referenced by v2 FKs. The two tables coexist; the
 * application is responsible for linking them (a future task). For now
 * the v2 FKs reference v2 `user.id` (integer autoincrement).
 */

import { sql } from "drizzle-orm";
import { integer, sqliteTable, text, uniqueIndex } from "drizzle-orm/sqlite-core";

export const user = sqliteTable(
  "v2_user",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    email: text("email").notNull(),
    nome: text("nome").notNull(),
    /** ISO8601 UTC TEXT, generated in app layer. */
    createdAt: text("created_at")
      .notNull(),
    updatedAt: text("updated_at")
      .notNull()
      .$onUpdate(() => new Date().toISOString()),
    /** Q2=B: soft-delete (LGPD). NULL = active. */
    deletedAt: text("deleted_at"),
  },
  (table) => ({
    /** Active email uniqueness; soft-deleted rows are excluded. */
    emailActiveUnique: uniqueIndex("uq_user_email_active")
      .on(table.email)
      .where(sql`${table.deletedAt} IS NULL`),
  })
);

// Type exports
export type User = typeof user.$inferSelect;
export type NewUser = typeof user.$inferInsert;
