/**
 * Recordings/Transactions (Lancamentos) Schema - SQLite Version
 *
 * SQLite Compatibility Notes:
 * - Uses `text` instead of `varchar`
 * - Uses `real` instead of `decimal` (SQLite has no true decimal)
 * - Uses `integer({ mode: 'boolean' })` for boolean fields
 * - Dates/timestamps stored as ISO 8601 text strings
 */

import { sqliteTable, text, integer, real, uniqueIndex } from 'drizzle-orm/sqlite-core';
import { sql } from 'drizzle-orm';
import { documento } from './documentos';
import { pessoas } from './pessoas';
import { cartorios } from './cartorios';

/**
 * Recording type definitions
 * Valid values for tipo: 'averbacao', 'registro', 'inicio_matricula'
 */
export const lancamentoTipo = sqliteTable('dominial_lancamentotipo', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  tipo: text('tipo').notNull(),
  requerTransmissao: integer('requer_transmissao', { mode: 'boolean' }).notNull().default(false),
  requerDetalhes: integer('requer_detalhes', { mode: 'boolean' }).notNull().default(false),
  requerTitulo: integer('requer_titulo', { mode: 'boolean' }).notNull().default(false),
  requerCartorioOrigem: integer('requer_cartorio_origem', { mode: 'boolean' })
    .notNull()
    .default(false),
  requerLivroOrigem: integer('requer_livro_origem', { mode: 'boolean' }).notNull().default(false),
  requerFolhaOrigem: integer('requer_folha_origem', { mode: 'boolean' }).notNull().default(false),
  requerDataOrigem: integer('requer_data_origem', { mode: 'boolean' }).notNull().default(false),
  requerForma: integer('requer_forma', { mode: 'boolean' }).notNull().default(false),
  requerDescricao: integer('requer_descricao', { mode: 'boolean' }).notNull().default(false),
  requerObservacao: integer('requer_observacao', { mode: 'boolean' }).notNull().default(true),
});

/**
 * Individual recordings within documents
 */
export const lancamento = sqliteTable('dominial_lancamento', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  documentoId: integer('documento_id')
    .notNull()
    .references(() => documento.id, { onDelete: 'cascade' }),
  tipoId: integer('tipo_id')
    .notNull()
    .references(() => lancamentoTipo.id, { onDelete: 'restrict' }),
  numeroLancamento: text('numero_lancamento'),
  data: text('data').notNull(), // DATE as ISO string

  /**
   * @deprecated Use LancamentoPessoa junction table with tipo='transmitente' instead.
   * Kept for backward compatibility with existing data.
   */
  transmitenteId: integer('transmitente_id').references(() => pessoas.id, {
    onDelete: 'restrict',
  }),
  /**
   * @deprecated Use LancamentoPessoa junction table with tipo='adquirente' instead.
   * Kept for backward compatibility with existing data.
   */
  adquirenteId: integer('adquirente_id').references(() => pessoas.id, {
    onDelete: 'restrict',
  }),

  valorTransacao: real('valor_transacao'), // Note: SQLite real has less precision
  area: real('area'),
  origem: text('origem'),
  detalhes: text('detalhes'),
  observacoes: text('observacoes'),
  dataCadastro: text('data_cadastro')
    .notNull()
    .default(sql`(date('now'))`),

  // Type-specific fields
  forma: text('forma'),
  descricao: text('descricao'),
  titulo: text('titulo'),

  // Cartorio fields by context
  cartorioOrigemId: integer('cartorio_origem_id').references(() => cartorios.id, {
    onDelete: 'restrict',
  }),
  /**
   * @deprecated Use cartorio_transmissao_id instead. This is a legacy field
   * with unclear naming. Kept for backward compatibility.
   */
  cartorioTransacaoId: integer('cartorio_transacao_id').references(() => cartorios.id, {
    onDelete: 'restrict',
  }),
  cartorioTransmissaoId: integer('cartorio_transmissao_id').references(() => cartorios.id, {
    onDelete: 'restrict',
  }), // New standard

  // Transaction fields
  livroTransacao: text('livro_transacao'),
  folhaTransacao: text('folha_transacao'),
  dataTransacao: text('data_transacao'),

  // Origin fields (for inicio_matricula)
  livroOrigem: text('livro_origem'),
  folhaOrigem: text('folha_origem'),
  dataOrigem: text('data_origem'),

  // Control flags
  ehInicioMatricula: integer('eh_inicio_matricula', { mode: 'boolean' }).notNull().default(false),

  // Link to origin document (for chain tracking)
  documentoOrigemId: integer('documento_origem_id').references(() => documento.id, {
    onDelete: 'restrict',
  }),
});

/**
 * Multiple people per recording (many-to-many with roles)
 */
export const lancamentoPessoa = sqliteTable(
  'dominial_lancamentopessoa',
  {
    id: integer('id').primaryKey({ autoIncrement: true }),
    lancamentoId: integer('lancamento_id')
      .notNull()
      .references(() => lancamento.id, { onDelete: 'cascade' }),
    pessoaId: integer('pessoa_id')
      .notNull()
      .references(() => pessoas.id, { onDelete: 'restrict' }),
    tipo: text('tipo').notNull(), // 'transmitente' or 'adquirente'
    nomeDigitado: text('nome_digitado'),
  },
  (table) => ({
    uniqueLancamentoPessoaTipo: uniqueIndex('unique_lancamento_pessoa_tipo').on(
      table.lancamentoId,
      table.pessoaId,
      table.tipo
    ),
  })
);

/**
 * End of chain information per origin in a recording
 */
export const origemFimCadeia = sqliteTable(
  'dominial_origemfimcadeia',
  {
    id: integer('id').primaryKey({ autoIncrement: true }),
    lancamentoId: integer('lancamento_id')
      .notNull()
      .references(() => lancamento.id, { onDelete: 'cascade' }),
    indiceOrigem: integer('indice_origem').notNull(),
    fimCadeia: integer('fim_cadeia', { mode: 'boolean' }).notNull().default(false),
    tipoFimCadeia: text('tipo_fim_cadeia'), // 'destacamento_publico', 'outra', 'sem_origem'
    especificacaoFimCadeia: text('especificacao_fim_cadeia'),
    classificacaoFimCadeia: text('classificacao_fim_cadeia'), // 'origem_lidima', 'sem_origem', 'inconclusa'
  },
  (table) => ({
    uniqueLancamentoOrigem: uniqueIndex('unique_lancamento_origem').on(
      table.lancamentoId,
      table.indiceOrigem
    ),
  })
);

/**
 * Master list of end-of-chain types
 */
export const fimCadeia = sqliteTable('dominial_fimcadeia', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  nome: text('nome').notNull().unique(),
  tipo: text('tipo').notNull().default('destacamento_publico'), // 'destacamento_publico', 'outra', 'sem_origem'
  classificacao: text('classificacao').notNull().default('origem_lidima'), // 'origem_lidima', 'sem_origem', 'inconclusa'
  sigla: text('sigla'),
  descricao: text('descricao'),
  ativo: integer('ativo', { mode: 'boolean' }).notNull().default(true),
  dataCriacao: text('data_criacao')
    .notNull()
    .default(sql`(datetime('now'))`),
  /** Auto-updated timestamp via $onUpdate() for Drizzle operations */
  dataAtualizacao: text('data_atualizacao')
    .notNull()
    .default(sql`(datetime('now'))`)
    .$onUpdate(() => new Date().toISOString()),
});

// Type exports
export type LancamentoTipo = typeof lancamentoTipo.$inferSelect;
export type NewLancamentoTipo = typeof lancamentoTipo.$inferInsert;
export type Lancamento = typeof lancamento.$inferSelect;
export type NewLancamento = typeof lancamento.$inferInsert;
export type LancamentoPessoa = typeof lancamentoPessoa.$inferSelect;
export type NewLancamentoPessoa = typeof lancamentoPessoa.$inferInsert;
export type OrigemFimCadeia = typeof origemFimCadeia.$inferSelect;
export type NewOrigemFimCadeia = typeof origemFimCadeia.$inferInsert;
export type FimCadeia = typeof fimCadeia.$inferSelect;
export type NewFimCadeia = typeof fimCadeia.$inferInsert;
