/**
 * Recordings/Transactions (Lancamentos) Schema
 */

import {
  pgTable,
  serial,
  varchar,
  text,
  date,
  timestamp,
  integer,
  decimal,
  boolean,
  unique,
} from 'drizzle-orm/pg-core';
import { sql } from 'drizzle-orm';
import { documento } from './documentos';
import { pessoas } from './pessoas';
import { cartorios } from './cartorios';

/**
 * Recording type definitions
 */
export const lancamentoTipo = pgTable('dominial_lancamentotipo', {
  id: serial('id').primaryKey(),
  tipo: varchar('tipo', { length: 50 }).notNull(), // 'averbacao', 'registro', 'inicio_matricula'
  requerTransmissao: boolean('requer_transmissao').notNull().default(false),
  requerDetalhes: boolean('requer_detalhes').notNull().default(false),
  requerTitulo: boolean('requer_titulo').notNull().default(false),
  requerCartorioOrigem: boolean('requer_cartorio_origem').notNull().default(false),
  requerLivroOrigem: boolean('requer_livro_origem').notNull().default(false),
  requerFolhaOrigem: boolean('requer_folha_origem').notNull().default(false),
  requerDataOrigem: boolean('requer_data_origem').notNull().default(false),
  requerForma: boolean('requer_forma').notNull().default(false),
  requerDescricao: boolean('requer_descricao').notNull().default(false),
  requerObservacao: boolean('requer_observacao').notNull().default(true),
});

/**
 * Individual recordings within documents
 */
export const lancamento = pgTable('dominial_lancamento', {
  id: serial('id').primaryKey(),
  documentoId: integer('documento_id')
    .notNull()
    .references(() => documento.id, { onDelete: 'cascade' }),
  tipoId: integer('tipo_id')
    .notNull()
    .references(() => lancamentoTipo.id, { onDelete: 'restrict' }),
  numeroLancamento: varchar('numero_lancamento', { length: 50 }),
  data: date('data').notNull(),

  // Legacy single person fields
  transmitenteId: integer('transmitente_id').references(() => pessoas.id, {
    onDelete: 'restrict',
  }),
  adquirenteId: integer('adquirente_id').references(() => pessoas.id, {
    onDelete: 'restrict',
  }),

  valorTransacao: decimal('valor_transacao', { precision: 10, scale: 2 }),
  area: decimal('area', { precision: 12, scale: 4 }),
  origem: varchar('origem', { length: 255 }),
  detalhes: text('detalhes'),
  observacoes: text('observacoes'),
  dataCadastro: date('data_cadastro').default(sql`CURRENT_DATE`).notNull(),

  // Type-specific fields
  forma: varchar('forma', { length: 100 }),
  descricao: text('descricao'),
  titulo: varchar('titulo', { length: 255 }),

  // Cartorio fields by context
  cartorioOrigemId: integer('cartorio_origem_id').references(() => cartorios.id, {
    onDelete: 'restrict',
  }),
  cartorioTransacaoId: integer('cartorio_transacao_id').references(
    () => cartorios.id,
    { onDelete: 'restrict' }
  ), // Legacy
  cartorioTransmissaoId: integer('cartorio_transmissao_id').references(
    () => cartorios.id,
    { onDelete: 'restrict' }
  ), // New standard

  // Transaction fields
  livroTransacao: varchar('livro_transacao', { length: 50 }),
  folhaTransacao: varchar('folha_transacao', { length: 50 }),
  dataTransacao: date('data_transacao'),

  // Origin fields (for inicio_matricula)
  livroOrigem: varchar('livro_origem', { length: 50 }),
  folhaOrigem: varchar('folha_origem', { length: 50 }),
  dataOrigem: date('data_origem'),

  // Control flags
  ehInicioMatricula: boolean('eh_inicio_matricula').notNull().default(false),

  // Link to origin document (for chain tracking)
  documentoOrigemId: integer('documento_origem_id').references(
    () => documento.id,
    { onDelete: 'restrict' }
  ),
});

/**
 * Multiple people per recording (many-to-many with roles)
 */
export const lancamentoPessoa = pgTable(
  'dominial_lancamentopessoa',
  {
    id: serial('id').primaryKey(),
    lancamentoId: integer('lancamento_id')
      .notNull()
      .references(() => lancamento.id, { onDelete: 'cascade' }),
    pessoaId: integer('pessoa_id')
      .notNull()
      .references(() => pessoas.id, { onDelete: 'restrict' }),
    tipo: varchar('tipo', { length: 20 }).notNull(), // 'transmitente' or 'adquirente'
    nomeDigitado: varchar('nome_digitado', { length: 255 }),
  },
  (table) => [unique().on(table.lancamentoId, table.pessoaId, table.tipo)]
);

/**
 * End of chain information per origin in a recording
 */
export const origemFimCadeia = pgTable(
  'dominial_origemfimcadeia',
  {
    id: serial('id').primaryKey(),
    lancamentoId: integer('lancamento_id')
      .notNull()
      .references(() => lancamento.id, { onDelete: 'cascade' }),
    indiceOrigem: integer('indice_origem').notNull(),
    fimCadeia: boolean('fim_cadeia').notNull().default(false),
    tipoFimCadeia: varchar('tipo_fim_cadeia', { length: 50 }), // 'destacamento_publico', 'outra', 'sem_origem'
    especificacaoFimCadeia: text('especificacao_fim_cadeia'),
    classificacaoFimCadeia: varchar('classificacao_fim_cadeia', { length: 50 }), // 'origem_lidima', 'sem_origem', 'inconclusa'
  },
  (table) => [unique().on(table.lancamentoId, table.indiceOrigem)]
);

/**
 * Master list of end-of-chain types
 */
export const fimCadeia = pgTable('dominial_fimcadeia', {
  id: serial('id').primaryKey(),
  nome: varchar('nome', { length: 100 }).notNull().unique(),
  tipo: varchar('tipo', { length: 50 }).notNull().default('destacamento_publico'), // 'destacamento_publico', 'outra', 'sem_origem'
  classificacao: varchar('classificacao', { length: 50 })
    .notNull()
    .default('origem_lidima'), // 'origem_lidima', 'sem_origem', 'inconclusa'
  sigla: varchar('sigla', { length: 50 }),
  descricao: text('descricao'),
  ativo: boolean('ativo').notNull().default(true),
  dataCriacao: timestamp('data_criacao').defaultNow().notNull(),
  dataAtualizacao: timestamp('data_atualizacao').defaultNow().notNull(),
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
