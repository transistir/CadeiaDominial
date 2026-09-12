/**
 * Documents Schema - SQLite Version
 *
 * SQLite Compatibility Notes:
 * - Uses `text` instead of `varchar`
 * - Uses SQLite-specific unique/index syntax
 * - Dates stored as ISO 8601 text strings
 */

import { sqliteTable, text, integer, uniqueIndex, index } from 'drizzle-orm/sqlite-core';
import { sql } from 'drizzle-orm';
import { imovel } from './imovel';
import { cartorios } from './cartorios';

/**
 * Document type definitions
 * Valid values: 'transcricao', 'matricula'
 */
export const documentoTipo = sqliteTable('dominial_documentotipo', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  tipo: text('tipo').notNull(), // 'transcricao' or 'matricula'
});

/**
 * Registration documents (matriculas and transcricoes)
 */
export const documento = sqliteTable(
  'dominial_documento',
  {
    id: integer('id').primaryKey({ autoIncrement: true }),
    imovelId: integer('imovel_id')
      .notNull()
      .references(() => imovel.id, { onDelete: 'cascade' }),
    tipoId: integer('tipo_id')
      .notNull()
      .references(() => documentoTipo.id, { onDelete: 'restrict' }),
    numero: text('numero').notNull(),
    data: text('data').notNull(), // DATE as ISO string (YYYY-MM-DD)
    cartorioId: integer('cartorio_id')
      .notNull()
      .references(() => cartorios.id, { onDelete: 'restrict' }),
    livro: text('livro').notNull(),
    folha: text('folha').notNull(),
    origem: text('origem'),
    observacoes: text('observacoes'),
    dataCadastro: text('data_cadastro')
      .notNull()
      .default(sql`(date('now'))`),
    nivelManual: integer('nivel_manual'), // 0-10
    classificacaoFimCadeia: text('classificacao_fim_cadeia'), // 'origem_lidima', 'sem_origem', 'inconclusa'
    siglaPatrimonioPublico: text('sigla_patrimonio_publico'),
    criAtualId: integer('cri_atual_id').references(() => cartorios.id, {
      onDelete: 'restrict',
    }),
    criOrigemId: integer('cri_origem_id').references(() => cartorios.id, {
      onDelete: 'restrict',
    }),
  },
  (table) => ({
    uniqueNumeroCartorio: uniqueIndex('unique_numero_cartorio').on(table.numero, table.cartorioId),
  })
);

/**
 * Tracks documents imported from other property chains
 */
export const documentoImportado = sqliteTable(
  'dominial_documentoimportado',
  {
    id: integer('id').primaryKey({ autoIncrement: true }),
    documentoId: integer('documento_id')
      .notNull()
      .references(() => documento.id, { onDelete: 'cascade' }),
    imovelOrigemId: integer('imovel_origem_id')
      .notNull()
      .references(() => imovel.id, { onDelete: 'cascade' }),
    dataImportacao: text('data_importacao')
      .notNull()
      .default(sql`(datetime('now'))`),
    importadoPorId: integer('importado_por_id'), // FK to auth_user - handled separately
  },
  (table) => ({
    uniqueDocumentoImovelOrigem: uniqueIndex('unique_documento_imovel_origem').on(
      table.documentoId,
      table.imovelOrigemId
    ),
    documentoIdIdx: index('idx_documento_importado_documento').on(table.documentoId),
    imovelOrigemIdIdx: index('idx_documento_importado_imovel').on(table.imovelOrigemId),
    dataImportacaoIdx: index('idx_documento_importado_data').on(table.dataImportacao),
    importadoPorIdIdx: index('idx_documento_importado_user').on(table.importadoPorId),
  })
);

// Type exports
export type DocumentoTipo = typeof documentoTipo.$inferSelect;
export type NewDocumentoTipo = typeof documentoTipo.$inferInsert;
export type Documento = typeof documento.$inferSelect;
export type NewDocumento = typeof documento.$inferInsert;
export type DocumentoImportado = typeof documentoImportado.$inferSelect;
export type NewDocumentoImportado = typeof documentoImportado.$inferInsert;
