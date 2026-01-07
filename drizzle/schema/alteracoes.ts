/**
 * Amendments/Changes (Alteracoes) Schema
 */

import {
  pgTable,
  serial,
  varchar,
  text,
  date,
  integer,
  decimal,
} from 'drizzle-orm/pg-core';
import { imovel } from './imovel';
import { cartorios } from './cartorios';
import { pessoas } from './pessoas';

/**
 * Amendment type definitions
 */
export const alteracoesTipo = pgTable('dominial_alteracoestipo', {
  id: serial('id').primaryKey(),
  tipo: varchar('tipo', { length: 50 }).notNull(), // 'registro', 'averbacao', 'nao_classificado'
});

/**
 * Registration type definitions
 */
export const registroTipo = pgTable('dominial_registrotipo', {
  id: serial('id').primaryKey(),
  tipo: varchar('tipo', { length: 100 }).notNull(),
});

/**
 * Notation type definitions
 */
export const averbacoesTipo = pgTable('dominial_averbacaotipo', {
  id: serial('id').primaryKey(),
  tipo: varchar('tipo', { length: 100 }).notNull(),
});

/**
 * Property amendments/changes
 */
export const alteracoes = pgTable('dominial_alteracoes', {
  id: serial('id').primaryKey(),
  imovelIdId: integer('imovel_id_id')
    .notNull()
    .references(() => imovel.id, { onDelete: 'cascade' }),
  tipoAlteracaoIdId: integer('tipo_alteracao_id_id')
    .notNull()
    .references(() => alteracoesTipo.id, { onDelete: 'cascade' }),
  livro: varchar('livro', { length: 50 }),
  folha: varchar('folha', { length: 50 }),
  cartorioId: integer('cartorio_id')
    .notNull()
    .references(() => cartorios.id, { onDelete: 'cascade' }),
  dataAlteracao: date('data_alteracao'),
  registroTipoId: integer('registro_tipo_id').references(() => registroTipo.id, {
    onDelete: 'cascade',
  }),
  averbacaoTipoId: integer('averbacao_tipo_id').references(
    () => averbacoesTipo.id,
    { onDelete: 'cascade' }
  ),
  titulo: varchar('titulo', { length: 255 }),
  cartorioOrigemId: integer('cartorio_origem_id')
    .notNull()
    .references(() => cartorios.id, { onDelete: 'cascade' }),
  livroOrigem: varchar('livro_origem', { length: 50 }),
  folhaOrigem: varchar('folha_origem', { length: 50 }),
  dataOrigem: date('data_origem'),
  transmitenteId: integer('transmitente_id').references(() => pessoas.id, {
    onDelete: 'cascade',
  }),
  adquirenteId: integer('adquirente_id').references(() => pessoas.id, {
    onDelete: 'cascade',
  }),
  valorTransacao: decimal('valor_transacao', { precision: 10, scale: 2 }),
  area: decimal('area', { precision: 12, scale: 4 }),
  observacoes: text('observacoes'),
  dataCadastro: date('data_cadastro').defaultNow().notNull(),
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
