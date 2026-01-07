/**
 * Indigenous Lands (Terras Indigenas) Schema
 */

import {
  pgTable,
  serial,
  varchar,
  text,
  date,
  timestamp,
  integer,
  real,
  decimal,
  unique,
} from 'drizzle-orm/pg-core';

/**
 * Reference data for Indigenous lands imported from government sources
 */
export const terraIndigenaReferencia = pgTable('dominial_terraindigenareferencia', {
  id: serial('id').primaryKey(),
  codigo: varchar('codigo', { length: 50 }).notNull().unique(),
  nome: varchar('nome', { length: 255 }).notNull(),
  etnia: varchar('etnia', { length: 255 }),
  estado: varchar('estado', { length: 100 }),
  municipio: varchar('municipio', { length: 255 }),
  areaHa: real('area_ha'),
  fase: varchar('fase', { length: 100 }),
  modalidade: varchar('modalidade', { length: 100 }),
  coordenacaoRegional: varchar('coordenacao_regional', { length: 100 }),
  dataRegularizada: date('data_regularizada'),
  dataHomologada: date('data_homologada'),
  dataDeclarada: date('data_declarada'),
  dataDelimitada: date('data_delimitada'),
  dataEmEstudo: date('data_em_estudo'),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
});

/**
 * Working records for Indigenous lands being analyzed
 */
export const tis = pgTable('dominial_tis', {
  id: serial('id').primaryKey(),
  terraReferenciaId: integer('terra_referencia_id').references(
    () => terraIndigenaReferencia.id,
    { onDelete: 'restrict' }
  ),
  nome: varchar('nome', { length: 255 }).notNull(),
  codigo: varchar('codigo', { length: 50 }).notNull().unique(),
  etnia: varchar('etnia', { length: 255 }).notNull(),
  estado: varchar('estado', { length: 100 }),
  area: decimal('area', { precision: 12, scale: 2 }),
  dataCadastro: date('data_cadastro').defaultNow().notNull(),
});

// Type exports
export type TerraIndigenaReferencia = typeof terraIndigenaReferencia.$inferSelect;
export type NewTerraIndigenaReferencia = typeof terraIndigenaReferencia.$inferInsert;
export type TIs = typeof tis.$inferSelect;
export type NewTIs = typeof tis.$inferInsert;
