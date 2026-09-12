/**
 * Indigenous Lands (Terras Indigenas) Schema - SQLite Version
 *
 * SQLite Compatibility Notes:
 * - Uses `text` instead of `varchar` (SQLite doesn't enforce length limits)
 * - Uses `real` instead of `decimal` (SQLite has no true decimal type)
 * - Uses `text` for timestamps (stored as ISO 8601 strings)
 * - Uses `integer().primaryKey({ autoIncrement: true })` instead of `serial`
 */

import { sqliteTable, text, integer, real } from 'drizzle-orm/sqlite-core';
import { sql } from 'drizzle-orm';

/**
 * Reference data for Indigenous lands imported from government sources
 */
export const terraIndigenaReferencia = sqliteTable('dominial_terraindigenareferencia', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  codigo: text('codigo').notNull().unique(),
  nome: text('nome').notNull(),
  etnia: text('etnia'),
  estado: text('estado'),
  municipio: text('municipio'),
  areaHa: real('area_ha'),
  fase: text('fase'),
  modalidade: text('modalidade'),
  coordenacaoRegional: text('coordenacao_regional'),
  dataRegularizada: text('data_regularizada'), // DATE as ISO string
  dataHomologada: text('data_homologada'),
  dataDeclarada: text('data_declarada'),
  dataDelimitada: text('data_delimitada'),
  dataEmEstudo: text('data_em_estudo'),
  createdAt: text('created_at')
    .notNull()
    .default(sql`(datetime('now'))`),
  /**
   * Auto-updated timestamp. Django handles this via `auto_now=True`.
   * The `$onUpdate()` ensures Drizzle also auto-updates this field.
   */
  updatedAt: text('updated_at')
    .notNull()
    .default(sql`(datetime('now'))`)
    .$onUpdate(() => new Date().toISOString()),
});

/**
 * Working records for Indigenous lands being analyzed
 */
export const tis = sqliteTable('dominial_tis', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  terraReferenciaId: integer('terra_referencia_id').references(
    () => terraIndigenaReferencia.id,
    { onDelete: 'restrict' }
  ),
  nome: text('nome').notNull(),
  codigo: text('codigo').notNull().unique(),
  etnia: text('etnia').notNull(),
  estado: text('estado'),
  area: real('area'), // Note: SQLite real has less precision than decimal(12,2)
  dataCadastro: text('data_cadastro')
    .notNull()
    .default(sql`(date('now'))`),
});

// Type exports
export type TerraIndigenaReferencia = typeof terraIndigenaReferencia.$inferSelect;
export type NewTerraIndigenaReferencia = typeof terraIndigenaReferencia.$inferInsert;
export type TIs = typeof tis.$inferSelect;
export type NewTIs = typeof tis.$inferInsert;
