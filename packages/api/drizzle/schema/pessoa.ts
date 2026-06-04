/**
 * Pessoa (cartório person entity) Schema
 *
 * Q5=REMOVER: v2 `pessoa` has ONLY `nome` plus id/timestamps/soft-delete.
 * NO cpf, rg, data_nascimento, email, telefone. The PR #12 schema had
 * these PII fields — they are REMOVED per Q5.
 *
 * Q4: PII encryption NOT applied. v2 pessoa only has `nome`, which is
 * public-by-definition in cartório (researcher attribution source).
 *
 * Q2=B: soft-delete via `deleted_at`. LGPD: NULL + deleted_at fills
 * rather than hard-delete, to preserve FK integrity.
 *
 * D3: pessoa is the CARTÓRIO entity (e.g. owner, transmitente, adquirente).
 * It is distinct from `user` (the system researcher). FKs to pessoa come
 * from `imovel.proprietario_id` and `lancamento_pessoa.pessoa_id`.
 *
 * T3: NO FTS5 sync triggers yet (FTS5 sync is a separate task; T-101 does
 * NOT create virtual FTS5 tables). FTS5 sync will be added later.
 */

import { integer, sqliteTable, text } from "drizzle-orm/sqlite-core";

export const pessoa = sqliteTable("pessoa", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  /** UNICO campo PII (Q5=REMOVER cpf/rg/data_nascimento/email/telefone). */
  nome: text("nome").notNull(),
  /** ISO8601 UTC TEXT, generated in app layer. */
  createdAt: text("created_at")
    .notNull(),
  updatedAt: text("updated_at")
    .notNull()
    .$onUpdate(() => new Date().toISOString()),
  /** Q2=B: soft-delete (LGPD). NULL = active. */
  deletedAt: text("deleted_at"),
});

// Type exports
export type Pessoa = typeof pessoa.$inferSelect;
export type NewPessoa = typeof pessoa.$inferInsert;
