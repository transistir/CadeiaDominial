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
 * DB-level CHECK on `papel` is declared via Drizzle's `check()` API and
 * emitted into the generated migration by `drizzle-kit generate` (the
 * migration `.sql` is git-ignored by project policy).
 */

import { sql } from "drizzle-orm";
import { integer, sqliteTable, text, check } from "drizzle-orm/sqlite-core";
import { lancamento } from "./lancamento";
import { pessoa } from "./pessoa";

export const lancamentoPessoa = sqliteTable(
  "lancamento_pessoa",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    /**
     * DB-level CHECK (emitted by `drizzle-kit generate` from the `check()`
     * below) — Drizzle `text({ enum: [...] })` is TS-only. The list of
     * roles is FIXED in v2.
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
      .notNull(),
    /**
     * Q2=B: soft-delete. Q7b=B: NOT cascaded on Imovel delete (L's are
     * preserved anyway, and this junction is a per-L relationship, not
     * per-I).
     */
    deletedAt: text("deleted_at"),
  },
  (table) => ({
    papelCheck: check(
      "lancamento_pessoa_papel_check",
      sql`${table.papel} IN ('transmitente', 'adquirente', 'outorgante', 'outorgado', 'anuente', 'testemunha')`
    ),
  })
);

// Type exports
export type LancamentoPessoa = typeof lancamentoPessoa.$inferSelect;
export type NewLancamentoPessoa = typeof lancamentoPessoa.$inferInsert;
