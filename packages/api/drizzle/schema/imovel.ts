/**
 * Imovel (Property) Schema
 *
 * Q11b=B: `imovel.cri_id` is a direct FK, FIXO (no history in v1). If v2+
 * needs historical CRI changes, create an `imovel_cri_historico` table then.
 *
 * Q7b=B: Cascade-conservative delete. Soft-delete of an Imovel cascades
 * to junctions (`imovel_documento`, `tis_imovel`) only. Lançamentos,
 * LancamentoPessoa, Documentos, Pessoas, CRIs are NOT touched (preserved
 * as orphans). Hard-delete is admin-only.
 *
 * Q2=B: `deleted_at` for soft-delete.
 *
 * Q8=A: Restore is symmetric to soft-delete (Q7b=B).
 *
 * Q9=C: `delete_operation_id` references `audit_log.id` for provenance of
 * the soft-delete action. SET NULL if the audit log is purged (LGPD).
 *
 * `proprietario_id` is SET NULL on `pessoa` delete: Q2=B allows LGPD
 * anonymization of a pessoa, in which case the imovel still exists but
 * has no current owner (researcher notes can fill the gap).
 *
 * `arquivado` is 0/1 with CHECK in (0,1).
 *
 * `data_cadastro` is a partial date (cartório convention per T3).
 */

import { sql } from "drizzle-orm";
import { integer, sqliteTable, text, uniqueIndex, check } from "drizzle-orm/sqlite-core";
import { cri } from "./cri";
import { pessoa } from "./pessoa";
import { auditLog } from "./audit_log";

export const imovel = sqliteTable(
  "imovel",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    nome: text("nome").notNull(),
    observacoes: text("observacoes"),
    /** Partial date per T3 (cartório: 'YYYY-MM-DD' | 'YYYY-MM' | 'YYYY'). */
    dataCadastro: text("data_cadastro"),
    /**
     * Q11b=B: fixed CRI for the property (no historical changes in v1).
     * RESTRICT prevents deletion of a CRI while Imóveis reference it.
     */
    criId: integer("cri_id")
      .notNull()
      .references(() => cri.id, { onDelete: "restrict" }),
    /**
     * Current owner. NULL allowed: if the pessoa is LGPD-anonymized
     * (Q2=B), the imovel still exists; researcher notes fill the gap.
     */
    proprietarioId: integer("proprietario_id").references(() => pessoa.id, {
      onDelete: "set null",
    }),
    /** 0/1 boolean. CHECK (arquivado IN (0,1)) enforced in migration. */
    arquivado: integer("arquivado", { mode: "boolean" })
      .notNull()
      .default(false),
    createdAt: text("created_at")
      .notNull(),
    updatedAt: text("updated_at")
      .notNull()
      .$onUpdate(() => new Date().toISOString()),
    /** Q2=B: soft-delete. */
    deletedAt: text("deleted_at"),
    /** Q9+C+Q8=A: provenance of the soft-delete. SET NULL if audit purged. */
    deleteOperationId: integer("delete_operation_id").references(
      () => auditLog.id,
      { onDelete: "set null" }
    ),
  },
  (table) => ({
    arquivadoCheck: check("imovel_arquivado_check", sql`${table.arquivado} IN (0, 1)`),
  })
);

// Type exports
export type Imovel = typeof imovel.$inferSelect;
export type NewImovel = typeof imovel.$inferInsert;
