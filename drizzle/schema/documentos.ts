/**
 * Documents Schema
 */

import {
  pgTable,
  serial,
  varchar,
  text,
  date,
  timestamp,
  integer,
  unique,
  index,
} from 'drizzle-orm/pg-core';
import { sql } from 'drizzle-orm';
import { imovel } from './imovel';
import { cartorios } from './cartorios';

/**
 * Document type definitions
 */
export const documentoTipo = pgTable('dominial_documentotipo', {
  id: serial('id').primaryKey(),
  tipo: varchar('tipo', { length: 50 }).notNull(), // 'transcricao' or 'matricula'
});

/**
 * Registration documents (matriculas and transcricoes)
 */
export const documento = pgTable(
  'dominial_documento',
  {
    id: serial('id').primaryKey(),
    imovelId: integer('imovel_id')
      .notNull()
      .references(() => imovel.id, { onDelete: 'cascade' }),
    tipoId: integer('tipo_id')
      .notNull()
      .references(() => documentoTipo.id, { onDelete: 'restrict' }),
    numero: varchar('numero', { length: 50 }).notNull(),
    data: date('data').notNull(),
    cartorioId: integer('cartorio_id')
      .notNull()
      .references(() => cartorios.id, { onDelete: 'restrict' }),
    livro: varchar('livro', { length: 50 }).notNull(),
    folha: varchar('folha', { length: 50 }).notNull(),
    origem: text('origem'),
    observacoes: text('observacoes'),
    dataCadastro: date('data_cadastro').default(sql`CURRENT_DATE`).notNull(),
    nivelManual: integer('nivel_manual'),
    classificacaoFimCadeia: varchar('classificacao_fim_cadeia', { length: 50 }),
    siglaPatrimonioPublico: varchar('sigla_patrimonio_publico', { length: 50 }),
    criAtualId: integer('cri_atual_id').references(() => cartorios.id, {
      onDelete: 'restrict',
    }),
    criOrigemId: integer('cri_origem_id').references(() => cartorios.id, {
      onDelete: 'restrict',
    }),
  },
  (table) => [unique().on(table.numero, table.cartorioId)]
);

/**
 * Tracks documents imported from other property chains
 */
export const documentoImportado = pgTable(
  'dominial_documentoimportado',
  {
    id: serial('id').primaryKey(),
    documentoId: integer('documento_id')
      .notNull()
      .references(() => documento.id, { onDelete: 'cascade' }),
    imovelOrigemId: integer('imovel_origem_id')
      .notNull()
      .references(() => imovel.id, { onDelete: 'cascade' }),
    dataImportacao: timestamp('data_importacao').defaultNow().notNull(),
    importadoPorId: integer('importado_por_id'), // FK to auth_user - handled separately
  },
  (table) => [
    unique().on(table.documentoId, table.imovelOrigemId),
    index().on(table.documentoId),
    index().on(table.imovelOrigemId),
    index().on(table.dataImportacao),
    index().on(table.importadoPorId),
  ]
);

// Type exports
export type DocumentoTipo = typeof documentoTipo.$inferSelect;
export type NewDocumentoTipo = typeof documentoTipo.$inferInsert;
export type Documento = typeof documento.$inferSelect;
export type NewDocumento = typeof documento.$inferInsert;
export type DocumentoImportado = typeof documentoImportado.$inferSelect;
export type NewDocumentoImportado = typeof documentoImportado.$inferInsert;
