/**
 * TIs (Indigenous Land working records) Schema
 *
 * TIs are working records for Indigenous lands being analyzed by
 * researchers. They may be linked to a `terra_indigena_referencia` for
 * official data, or created independently.
 *
 * No soft-delete (Q2: TIs are working data, not PII/legal records).
 * Area stored as integer centiares (T3 convention).
 *
 * FK actions: `terra_referencia_id → terra_indigena_referencia.id` is
 * RESTRICT (reference data cannot be removed while TIs reference it).
 */

import { sql } from "drizzle-orm";
import { integer, sqliteTable, text } from "drizzle-orm/sqlite-core";
import { terraIndigenaReferencia } from "./terra_indigena_referencia";

export const tis = sqliteTable("tis", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  codigo: text("codigo").notNull(),
  etnia: text("etnia").notNull(),
  /** Partial dates allowed (T3): 'YYYY-MM-DD' | 'YYYY-MM' | 'YYYY'. */
  dataCadastro: text("data_cadastro").notNull(),
  terraReferenciaId: integer("terra_referencia_id").references(
    () => terraIndigenaReferencia.id,
    { onDelete: "restrict" }
  ),
  /** Centiares (1 are = 100 m² → centiares = m² ÷ 1). */
  area: integer("area_centiares"),
  estado: text("estado"),
  nome: text("nome"),
  createdAt: text("created_at")
    .notNull()
    .default(sql`(current_timestamp)`),
  updatedAt: text("updated_at")
    .notNull()
    .default(sql`(current_timestamp)`)
    .$onUpdate(() => new Date().toISOString()),
});

// Type exports
export type Tis = typeof tis.$inferSelect;
export type NewTis = typeof tis.$inferInsert;
