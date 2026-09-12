/**
 * Amendments/Changes (Alteracoes) Schema - SQLite Version
 *
 * SQLite Compatibility Notes:
 * - Uses `text` instead of `varchar`
 * - Uses `real` instead of `decimal`
 * - Dates stored as ISO 8601 text strings
 */

import { sqliteTable, text, integer, real } from 'drizzle-orm/sqlite-core';
import { sql } from 'drizzle-orm';
import { imovel } from './imovel';
import { cartorios } from './cartorios';
import { pessoas } from './pessoas';

/**
 * Amendment type definitions
 * Valid values: 'registro', 'averbacao', 'nao_classificado'
 */
export const alteracoesTipo = sqliteTable('dominial_alteracoestipo', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  tipo: text('tipo').notNull(),
});

/**
 * Registration type definitions
 */
export const registroTipo = sqliteTable('dominial_registrotipo', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  tipo: text('tipo').notNull(),
});

/**
 * Notation type definitions
 */
export const averbacoesTipo = sqliteTable('dominial_averbacoestipo', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  tipo: text('tipo').notNull(),
});

/**
 * Property amendments/changes
 *
 * Note: Fields ending in `IdId` (e.g., imovelIdId) match Django's actual column names.
 * Django ForeignKey field `imovel_id` creates column `imovel_id_id`.
 */
export const alteracoes = sqliteTable('dominial_alteracoes', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  /** Django field `imovel_id` → column `imovel_id_id` */
  imovelIdId: integer('imovel_id_id')
    .notNull()
    .references(() => imovel.id, { onDelete: 'cascade' }),
  /** Django field `tipo_alteracao_id` → column `tipo_alteracao_id_id` */
  tipoAlteracaoIdId: integer('tipo_alteracao_id_id')
    .notNull()
    .references(() => alteracoesTipo.id, { onDelete: 'cascade' }),
  livro: text('livro'),
  folha: text('folha'),
  cartorioId: integer('cartorio_id')
    .notNull()
    .references(() => cartorios.id, { onDelete: 'cascade' }),
  dataAlteracao: text('data_alteracao'), // DATE as ISO string
  registroTipoId: integer('registro_tipo_id').references(() => registroTipo.id, {
    onDelete: 'cascade',
  }),
  averbacaoTipoId: integer('averbacao_tipo_id').references(() => averbacoesTipo.id, {
    onDelete: 'cascade',
  }),
  titulo: text('titulo'),
  cartorioOrigemId: integer('cartorio_origem_id')
    .notNull()
    .references(() => cartorios.id, { onDelete: 'cascade' }),
  livroOrigem: text('livro_origem'),
  folhaOrigem: text('folha_origem'),
  dataOrigem: text('data_origem'),
  transmitenteId: integer('transmitente_id').references(() => pessoas.id, {
    onDelete: 'cascade',
  }),
  adquirenteId: integer('adquirente_id').references(() => pessoas.id, {
    onDelete: 'cascade',
  }),
  valorTransacao: real('valor_transacao'), // Note: SQLite real has less precision
  area: real('area'),
  observacoes: text('observacoes'),
  dataCadastro: text('data_cadastro')
    .notNull()
    .default(sql`(date('now'))`),
});

// Type exports
export type AlteracoesTipo = typeof alteracoesTipo.$inferSelect;
export type NewAlteracoesTipo = typeof alteracoesTipo.$inferInsert;
export type RegistroTipo = typeof registroTipo.$inferSelect;
export type NewRegistroTipo = typeof registroTipo.$inferInsert;
export type AverbacoesTipo = typeof averbacoesTipo.$inferSelect;
export type NewAverbacoesTipo = typeof averbacoesTipo.$inferInsert;
export type Alteracao = typeof alteracoes.$inferSelect;
export type NewAlteracao = typeof alteracoes.$inferInsert;
