/**
 * Registry Offices (Cartorios) Schema - SQLite Version
 *
 * SQLite Compatibility Notes:
 * - No pgEnum - using text with comments for type values
 * - Uses `text` instead of `varchar`
 * - Timestamps stored as ISO 8601 text strings
 */

import { sqliteTable, text, integer } from 'drizzle-orm/sqlite-core';
import { sql } from 'drizzle-orm';

/**
 * Cartorio types (no pgEnum in SQLite, stored as text)
 * Valid values: 'CRI' (Cartorio de Registro de Imoveis), 'OUTRO'
 */

/**
 * Import status values (no pgEnum in SQLite, stored as text)
 * Valid values: 'pendente', 'em_andamento', 'concluido', 'erro'
 */

/**
 * Brazilian registry offices (cartorios)
 */
export const cartorios = sqliteTable('dominial_cartorios', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  nome: text('nome').notNull(),
  cns: text('cns').notNull().unique(), // National registry code
  endereco: text('endereco'),
  telefone: text('telefone'),
  email: text('email'),
  estado: text('estado'), // State code (2 chars: BA, SP, etc.)
  cidade: text('cidade'),
  tipo: text('tipo').notNull().default('CRI'), // 'CRI' or 'OUTRO'
});

/**
 * Batch import log for registry offices
 */
export const importacaoCartorios = sqliteTable('dominial_importacaocartorios', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  estado: text('estado').notNull(),
  dataInicio: text('data_inicio')
    .notNull()
    .default(sql`(datetime('now'))`),
  dataFim: text('data_fim'),
  totalCartorios: integer('total_cartorios').notNull().default(0),
  status: text('status').notNull().default('pendente'), // 'pendente', 'em_andamento', 'concluido', 'erro'
  erro: text('erro'),
});

// Type exports
export type Cartorio = typeof cartorios.$inferSelect;
export type NewCartorio = typeof cartorios.$inferInsert;
export type ImportacaoCartorio = typeof importacaoCartorios.$inferSelect;
export type NewImportacaoCartorio = typeof importacaoCartorios.$inferInsert;
