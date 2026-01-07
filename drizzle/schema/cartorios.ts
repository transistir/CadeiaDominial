/**
 * Registry Offices (Cartorios) Schema
 */

import {
  pgTable,
  serial,
  varchar,
  text,
  timestamp,
  integer,
  pgEnum,
} from 'drizzle-orm/pg-core';

/**
 * Enum for cartorio types
 */
export const cartorioTipoEnum = pgEnum('cartorio_tipo', ['CRI', 'OUTRO']);

/**
 * Enum for import status
 */
export const importStatusEnum = pgEnum('import_status', [
  'pendente',
  'em_andamento',
  'concluido',
  'erro',
]);

/**
 * Brazilian registry offices (cartorios)
 */
export const cartorios = pgTable('dominial_cartorios', {
  id: serial('id').primaryKey(),
  nome: varchar('nome', { length: 200 }).notNull(),
  cns: varchar('cns', { length: 20 }).notNull().unique(),
  endereco: varchar('endereco', { length: 200 }),
  telefone: varchar('telefone', { length: 20 }),
  email: varchar('email', { length: 254 }),
  estado: varchar('estado', { length: 2 }),
  cidade: varchar('cidade', { length: 100 }),
  tipo: varchar('tipo', { length: 10 }).notNull().default('CRI'),
});

/**
 * Batch import log for registry offices
 */
export const importacaoCartorios = pgTable('dominial_importacaocartorios', {
  id: serial('id').primaryKey(),
  estado: varchar('estado', { length: 2 }).notNull(),
  dataInicio: timestamp('data_inicio').defaultNow().notNull(),
  dataFim: timestamp('data_fim'),
  totalCartorios: integer('total_cartorios').notNull().default(0),
  status: varchar('status', { length: 20 }).notNull().default('pendente'),
  erro: text('erro'),
});

// Type exports
export type Cartorio = typeof cartorios.$inferSelect;
export type NewCartorio = typeof cartorios.$inferInsert;
export type ImportacaoCartorio = typeof importacaoCartorios.$inferSelect;
export type NewImportacaoCartorio = typeof importacaoCartorios.$inferInsert;
