/**
 * TerraIndigenaReferencia (Indigenous Land reference data) Schema
 *
 * Reference data for Indigenous lands imported from official government
 * sources (FUNAI). No soft-delete — this is external reference data.
 *
 * Area stored in centiares (1 ha = 100 are = 10000 m² → 1 are = 100 m²,
 * so 1 ha = 10000 centiares). Use integer for fixed-point precision.
 *
 * FK action on `tis.terra_referencia_id` is RESTRICT: a reference record
 * cannot be removed while TIs reference it.
 *
 * `area_ha` is named for the field's natural unit (hectares) but stored
 * as INTEGER centiares to match the convention in T3 (SQLite/D1 appendix).
 */

import { sql } from "drizzle-orm";
import { integer, sqliteTable, text, uniqueIndex } from "drizzle-orm/sqlite-core";

export const terraIndigenaReferencia = sqliteTable(
  "terra_indigena_referencia",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    codigo: text("codigo").notNull(),
    nome: text("nome").notNull(),
    etnia: text("etnia"),
    estado: text("estado"),
    municipio: text("municipio"),
    /**
     * Hectares stored as centiares (1 ha = 10000 centiares) to avoid
     * SQLite real precision loss. UI converts to hectares for display.
     */
    areaHa: integer("area_ha_centiares"),
    fase: text("fase"),
    modalidade: text("modalidade"),
    coordenacaoRegional: text("coordenacao_regional"),
    /** Partial dates allowed: 'YYYY-MM-DD' | 'YYYY-MM' | 'YYYY' — see T3. */
    dataRegularizada: text("data_regularizada"),
    dataHomologada: text("data_homologada"),
    dataDeclarada: text("data_declarada"),
    dataDelimitada: text("data_delimitada"),
    dataEmEstudo: text("data_em_estudo"),
    createdAt: text("created_at")
      .notNull()
      .default(sql`(current_timestamp)`),
    updatedAt: text("updated_at")
      .notNull()
      .default(sql`(current_timestamp)`)
      .$onUpdate(() => new Date().toISOString()),
  },
  (table) => ({
    codigoUnique: uniqueIndex("uq_terra_indigena_referencia_codigo").on(
      table.codigo
    ),
  })
);

// Type exports
export type TerraIndigenaReferencia = typeof terraIndigenaReferencia.$inferSelect;
export type NewTerraIndigenaReferencia = typeof terraIndigenaReferencia.$inferInsert;
