/**
 * LancamentoPessoa (Lancamento ↔ Pessoa junction) Schema
 *
 * Records the people involved in a Lancamento with their role:
 * transmitente (seller), adquirente (buyer), outorgante, outorgado,
 * anuente, testemunha.
 *
 * Q2=B: `nome_verbatim` is preserved EVEN IF `pessoa_id` is NULL (LGPD
 * anonymization). The junction row documents the participation with
 * the original transcribed name as evidence — the FK is optional.
 *
 * Q7b=B: `lancamento_id` is ON DELETE CASCADE (junction follows the
 * Lancamento on hard-delete — but Lancamentos are not hard-deleted in
 * normal flow, only via admin). `pessoa_id` is ON DELETE SET NULL
 * (Q2=B: anonymization, name preserved).
 *
 * CHECK (papel IN ('transmitente','adquirente','outorgante','outorgado',
 *                  'anuente','testemunha')) — enforced in migration.
 */

import { sql } from "drizzle-orm";
import { integer, sqliteTable, text } from "drizzle-orm/sqlite-core";
import { lancamento } from "./lancamento";
import { pessoa } from "./pessoa";

export const lancamentoPessoa = sqliteTable("lancamento_pessoa", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  /**
   * Role in the Lancamento. CHECK constraint in migration.
   */
  papel: text("papel", {
    enum: [
      "transmitente",
      "adquirente",
      "outorgante",
      "outorgado",
      "anuente",
      "testemunha",
    ],
  }).notNull(),
  /**
   * Q2=B: verbatim name preserved even when pessoa is anonymized (LGPD).
   * This is the evidence of who appeared on the cartório record.
   */
  nomeVerbatim: text("nome_verbatim").notNull(),
  /** CASCADE — junction follows the Lancamento. */
  lancamentoId: integer("lancamento_id")
    .notNull()
    .references(() => lancamento.id, { onDelete: "cascade" }),
  /**
   * SET NULL — LGPD anonymization. nome_verbatim remains.
   */
  pessoaId: integer("pessoa_id").references(() => pessoa.id, {
    onDelete: "set null",
  }),
  createdAt: text("created_at")
    .notNull()
    .default(sql`(current_timestamp)`),
  /**
   * Q2=B: soft-delete. Q7b=B: NOT cascaded on Imovel delete (L's are
   * preserved anyway, and this junction is a per-L relationship, not
   * per-I).
   */
  deletedAt: text("deleted_at"),
});

// Type exports
export type LancamentoPessoa = typeof lancamentoPessoa.$inferSelect;
export type NewLancamentoPessoa = typeof lancamentoPessoa.$inferInsert;
