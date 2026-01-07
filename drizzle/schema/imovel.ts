/**
 * Properties (Imoveis) Schema
 */

import {
  pgTable,
  serial,
  varchar,
  text,
  date,
  integer,
  boolean,
  unique,
  index,
} from 'drizzle-orm/pg-core';
import { tis } from './tis';
import { pessoas } from './pessoas';
import { cartorios } from './cartorios';

/**
 * Real estate properties being tracked in the system
 *
 * Note: The matricula is unique per cartorio, not globally.
 * This matches the Brazilian property registration system.
 */
export const imovel = pgTable(
  'dominial_imovel',
  {
    id: serial('id').primaryKey(),
    terraIndigenaIdId: integer('terra_indigena_id_id')
      .notNull()
      .references(() => tis.id, { onDelete: 'restrict' }),
    nome: varchar('nome', { length: 100 }).notNull(),
    proprietarioId: integer('proprietario_id')
      .notNull()
      .references(() => pessoas.id, { onDelete: 'restrict' }),
    matricula: varchar('matricula', { length: 50 }).notNull(),
    tipoDocumentoPrincipal: varchar('tipo_documento_principal', { length: 20 })
      .notNull()
      .default('matricula'),
    observacoes: text('observacoes'),
    cartorioId: integer('cartorio_id').references(() => cartorios.id, {
      onDelete: 'restrict',
    }),
    dataCadastro: date('data_cadastro').defaultNow().notNull(),
    arquivado: boolean('arquivado').notNull().default(false),
  },
  (table) => [
    unique('unique_matricula_por_cartorio').on(table.matricula, table.cartorioId),
    index('dom_imovel_mat_cart_idx').on(table.matricula, table.cartorioId),
  ]
);

/**
 * Junction table for many-to-many relationship between TIs and Properties
 */
export const tisImovel = pgTable('dominial_tis_imovel', {
  id: serial('id').primaryKey(),
  tisCodigoId: integer('tis_codigo_id')
    .notNull()
    .references(() => tis.id, { onDelete: 'cascade' }),
  imovelId: integer('imovel_id')
    .notNull()
    .references(() => imovel.id, { onDelete: 'cascade' }),
});

// Type exports
export type Imovel = typeof imovel.$inferSelect;
export type NewImovel = typeof imovel.$inferInsert;
export type TisImovel = typeof tisImovel.$inferSelect;
export type NewTisImovel = typeof tisImovel.$inferInsert;
