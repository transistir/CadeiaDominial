/**
 * Properties (Imoveis) Schema - SQLite Version
 *
 * SQLite Compatibility Notes:
 * - Uses `text` instead of `varchar`
 * - Uses SQLite-specific unique/index syntax
 * - Foreign key constraints work in SQLite but must be enabled via PRAGMA
 */

import { sqliteTable, text, integer, uniqueIndex, index } from 'drizzle-orm/sqlite-core';
import { sql } from 'drizzle-orm';
import { tis } from './tis';
import { pessoas } from './pessoas';
import { cartorios } from './cartorios';

/**
 * Real estate properties being tracked in the system
 *
 * Note: The matricula is unique per cartorio, not globally.
 * This matches the Brazilian property registration system.
 *
 * Django FK Naming Convention: When a Django ForeignKey field is named `foo_id`,
 * Django appends `_id` to create the database column `foo_id_id`. This results
 * in property names like `terraIndigenaIdId` which appear redundant but accurately
 * reflect the actual database column names.
 */
export const imovel = sqliteTable(
  'dominial_imovel',
  {
    id: integer('id').primaryKey({ autoIncrement: true }),
    /**
     * Note: The double "Id" suffix (terraIndigenaIdId) matches Django's actual
     * column name. Django field `terra_indigena_id` → column `terra_indigena_id_id`.
     */
    terraIndigenaIdId: integer('terra_indigena_id_id')
      .notNull()
      .references(() => tis.id, { onDelete: 'restrict' }),
    nome: text('nome').notNull(),
    proprietarioId: integer('proprietario_id')
      .notNull()
      .references(() => pessoas.id, { onDelete: 'restrict' }),
    matricula: text('matricula').notNull(),
    tipoDocumentoPrincipal: text('tipo_documento_principal')
      .notNull()
      .default('matricula'), // 'matricula' or 'transcricao'
    observacoes: text('observacoes'),
    cartorioId: integer('cartorio_id').references(() => cartorios.id, {
      onDelete: 'restrict',
    }),
    dataCadastro: text('data_cadastro')
      .notNull()
      .default(sql`(date('now'))`),
    arquivado: integer('arquivado', { mode: 'boolean' }).notNull().default(false),
  },
  (table) => ({
    uniqueMatriculaPorCartorio: uniqueIndex('unique_matricula_por_cartorio').on(
      table.matricula,
      table.cartorioId
    ),
    imovelMatCartIdx: index('dom_imovel_mat_cart_idx').on(table.matricula, table.cartorioId),
  })
);

/**
 * Junction table for many-to-many relationship between TIs and Properties
 */
export const tisImovel = sqliteTable('dominial_tis_imovel', {
  id: integer('id').primaryKey({ autoIncrement: true }),
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
