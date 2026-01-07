/**
 * Drizzle ORM Schema for Cadeia Dominial
 * Converted from Django models to Drizzle ORM (PostgreSQL)
 *
 * This file defines the complete database schema for the Indigenous Lands
 * Property Chain system using Drizzle ORM with PostgreSQL.
 *
 * @see https://orm.drizzle.team/docs/sql-schema-declaration
 * @see https://orm.drizzle.team/docs/relations-v2
 */

import { pgTable, serial, text, integer, varchar, boolean, decimal, date, timestamp, index, unique, uniqueIndex, primaryKey, pgEnum, foreignKey } from 'drizzle-orm/pg-core';
import { defineRelations } from 'drizzle-orm';

// =============================================================================
// ENUMS
// =============================================================================

export const tipoDocumentoEnum = pgEnum('tipo_documento_enum', ['matricula', 'transcricao']);

export const tipoImovelEnum = pgEnum('tipo_imovel_enum', ['matricula', 'transcricao']);

export const tipoCartorioEnum = pgEnum('tipo_cartorio_enum', ['CRI', 'OUTRO']);

export const tipoDocumentoTableEnum = pgEnum('tipo_documento_table_enum', ['transcricao', 'matricula']);

export const tipoLancamentoEnum = pgEnum('tipo_lancamento_enum', ['averbacao', 'registro', 'inicio_matricula']);

export const statusImportacaoEnum = pgEnum('status_importacao_enum', ['pendente', 'em_andamento', 'concluido', 'erro']);

export const tipoAlteracaoEnum = pgEnum('tipo_alteracao_enum', ['registro', 'averbacao', 'nao_classificado']);

export const classificacaoFimCadeiaEnum = pgEnum('classificacao_fim_cadeia_enum', ['origem_lidima', 'sem_origem', 'inconclusa']);

export const tipoFimCadeiaEnum = pgEnum('tipo_fim_cadeia_enum', ['destacamento_publico', 'outra', 'sem_origem']);

export const tipoLancamentoPessoaEnum = pgEnum('tipo_lancamento_pessoa_enum', ['transmitente', 'adquirente']);

// =============================================================================
// TABLES - Terra Indígena (Indigenous Lands)
// =============================================================================

/**
 * Reference data for Indigenous Lands
 * Imported from official sources
 */
export const terraIndigenaReferencia = pgTable('terraindigenareferencia', {
  id: serial('id').primaryKey(),
  codigo: varchar('codigo', { length: 50 }).notNull().unique(),
  nome: varchar('nome', { length: 255 }).notNull(),
  etnia: varchar('etnia', { length: 255 }),
  estado: varchar('estado', { length: 100 }),
  municipio: varchar('municipio', { length: 255 }),
  areaHa: decimal('area_ha', { precision: 12, scale: 2 }),
  fase: varchar('fase', { length: 100 }),
  modalidade: varchar('modalidade', { length: 100 }),
  coordenacaoRegional: varchar('coordenacao_regional', { length: 100 }),
  dataRegularizada: date('data_regularizada'),
  dataHomologada: date('data_homologada'),
  dataDeclarada: date('data_declarada'),
  dataDelimitada: date('data_delimitada'),
  dataEmEstudo: date('data_em_estudo'),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
}, (table) => [
  index('nome_idx').on(table.nome),
]);

/**
 * Active Indigenous Lands records
 * Auto-populated from TerraIndigenaReferencia
 */
export const tis = pgTable('tis', {
  id: serial('id').primaryKey(),
  terraReferenciaId: integer('terra_referencia_id').references(() => terraIndigenaReferencia.id, { onDelete: 'restrict' }),
  nome: varchar('nome', { length: 255 }).notNull(),
  codigo: varchar('codigo', { length: 50 }).notNull().unique(),
  etnia: varchar('etnia', { length: 255 }).notNull(),
  estado: varchar('estado', { length: 100 }), // comma-separated states
  area: decimal('area', { precision: 12, scale: 2 }),
  dataCadastro: date('data_cadastro').defaultNow().notNull(),
});

// =============================================================================
// TABLES - Pessoas (People)
// =============================================================================

/**
 * Property owners and transaction participants
 */
export const pessoas = pgTable('pessoas', {
  id: serial('id').primaryKey(),
  nome: varchar('nome', { length: 255 }).notNull(),
  cpf: varchar('cpf', { length: 11 }).unique(),
  rg: varchar('rg', { length: 20 }),
  dataNascimento: date('data_nascimento'),
  email: varchar('email', { length: 255 }),
  telefone: varchar('telefone', { length: 15 }),
}, (table) => [
  unique('cpf_unique').on(table.cpf),
]);

// =============================================================================
// TABLES - Cartórios (Registry Offices)
// =============================================================================

/**
 * Brazilian Registry Offices (Cartório de Registro de Imóveis)
 */
export const cartorios = pgTable('cartorios', {
  id: serial('id').primaryKey(),
  nome: varchar('nome', { length: 200 }).notNull(),
  cns: varchar('cns', { length: 20 }).notNull().unique(),
  endereco: varchar('endereco', { length: 200 }),
  telefone: varchar('telefone', { length: 20 }),
  email: varchar('email', { length: 255 }),
  estado: varchar('estado', { length: 2 }),
  cidade: varchar('cidade', { length: 100 }),
  tipo: tipoCartorioEnum('tipo').default('CRI').notNull(),
}, (table) => [
  index('cartorio_tipo_idx').on(table.tipo, table.estado, table.cidade, table.nome),
]);

/**
 * Track cartório import operations
 */
export const importacaoCartorios = pgTable('importacaocartorios', {
  id: serial('id').primaryKey(),
  estado: varchar('estado', { length: 2 }).notNull(),
  dataInicio: timestamp('data_inicio').defaultNow().notNull(),
  dataFim: timestamp('data_fim'),
  totalCartorios: integer('total_cartorios').default(0).notNull(),
  status: statusImportacaoEnum('status').default('pendente').notNull(),
  erro: text('erro'),
});

// =============================================================================
// TABLES - Imóveis (Properties)
// =============================================================================

/**
 * Properties belonging to Indigenous Lands
 * Matrícula must be unique per cartório, not globally
 */
export const imovel = pgTable('imovel', {
  id: serial('id').primaryKey(),
  terraIndigenaId: integer('terra_indigena_id').references(() => tis.id, { onDelete: 'restrict' }).notNull(),
  nome: varchar('nome', { length: 100 }).notNull(),
  proprietarioId: integer('proprietario').references(() => pessoas.id, { onDelete: 'restrict' }).notNull(),
  matricula: varchar('matricula', { length: 50 }).notNull(),
  tipoDocumentoPrincipal: tipoImovelEnum('tipo_documento_principal').default('matricula').notNull(),
  observacoes: text('observacoes'),
  cartorioId: integer('cartorio').references(() => cartorios.id, { onDelete: 'restrict' }),
  dataCadastro: date('data_cadastro').defaultNow().notNull(),
  arquivado: boolean('arquivado').default(false).notNull(),
}, (table) => [
  unique('unique_matricula_por_cartorio').on(table.matricula, table.cartorioId),
  index('imovel_matricula_idx').on(table.matricula, table.cartorioId),
]);

/**
 * Many-to-many relationship between TIs and Imóveis
 */
export const tisImovel = pgTable('tis_imovel', {
  id: serial('id').primaryKey(),
  tisCodigoId: integer('tis_codigo_id').references(() => tis.id, { onDelete: 'cascade' }).notNull(),
  imovelId: integer('imovel_id').references(() => imovel.id, { onDelete: 'cascade' }).notNull(),
});

// =============================================================================
// TABLES - Documentos (Documents)
// =============================================================================

/**
 * Document types
 */
export const documentoTipo = pgTable('documentotipo', {
  id: serial('id').primaryKey(),
  tipo: tipoDocumentoTableEnum('tipo').notNull(),
});

/**
 * Property documents (matrículas/transcrições)
 * Unique constraint: (numero, cartorio)
 */
export const documento = pgTable('documento', {
  id: serial('id').primaryKey(),
  imovelId: integer('imovel_id').references(() => imovel.id, { onDelete: 'cascade' }).notNull(),
  tipoId: integer('tipo_id').references(() => documentoTipo.id, { onDelete: 'restrict' }).notNull(),
  numero: varchar('numero', { length: 50 }).notNull(),
  data: date('data').notNull(),
  cartorioId: integer('cartorio_id').references(() => cartorios.id, { onDelete: 'restrict' }).notNull(),
  livro: varchar('livro', { length: 50 }).notNull(),
  folha: varchar('folha', { length: 50 }).notNull(),
  origem: text('origem'),
  observacoes: text('observacoes'),
  dataCadastro: date('data_cadastro').defaultNow().notNull(),
  nivelManual: integer('nivel_manual'),
  classificacaoFimCadeia: classificacaoFimCadeiaEnum('classificacao_fim_cadeia'),
  siglaPatrimonioPublico: varchar('sigla_patrimonio_publico', { length: 50 }),
  criAtualId: integer('cri_atual_id').references(() => cartorios.id, { onDelete: 'restrict' }),
  criOrigemId: integer('cri_origem_id').references(() => cartorios.id, { onDelete: 'restrict' }),
}, (table) => [
  unique('unique_documento_numero_cartorio').on(table.numero, table.cartorioId),
  index('documento_data_idx').on(table.data),
]);

/**
 * Track documents imported from other chains
 */
export const documentoImportado = pgTable('documentoimportado', {
  id: serial('id').primaryKey(),
  documentoId: integer('documento_id').references(() => documento.id, { onDelete: 'cascade' }).notNull(),
  imovelOrigemId: integer('imovel_origem_id').references(() => imovel.id, { onDelete: 'cascade' }).notNull(),
  dataImportacao: timestamp('data_importacao').defaultNow().notNull(),
  importadoPorId: integer('importado_por_id'),
}, (table) => [
  unique('unique_documento_importado').on(table.documentoId, table.imovelOrigemId),
  index('documento_importado_documento_idx').on(table.documentoId),
  index('documento_importado_imovel_origem_idx').on(table.imovelOrigemId),
  index('documento_importado_data_idx').on(table.dataImportacao),
  index('documento_importado_importador_idx').on(table.importadoPorId),
]);

// =============================================================================
// TABLES - Lançamentos (Transactions)
// =============================================================================

/**
 * Transaction types
 * Defines required fields for each transaction type
 */
export const lancamentoTipo = pgTable('lancamentotipo', {
  id: serial('id').primaryKey(),
  tipo: tipoLancamentoEnum('tipo').notNull(),
  requerTransmissao: boolean('requer_transmissao').default(false).notNull(),
  requerDetalhes: boolean('requer_detalhes').default(false).notNull(),
  requerTitulo: boolean('requer_titulo').default(false).notNull(),
  requerCartorioOrigem: boolean('requer_cartorio_origem').default(false).notNull(),
  requerLivroOrigem: boolean('requer_livro_origem').default(false).notNull(),
  requerFolhaOrigem: boolean('requer_folha_origem').default(false).notNull(),
  requerDataOrigem: boolean('requer_data_origem').default(false).notNull(),
  requerForma: boolean('requer_forma').default(false).notNull(),
  requerDescricao: boolean('requer_descricao').default(false).notNull(),
  requerObservacao: boolean('requer_observacao').default(true).notNull(),
});

/**
 * Transaction annotations on documents
 */
export const lancamento = pgTable('lancamento', {
  id: serial('id').primaryKey(),
  documentoId: integer('documento_id').references(() => documento.id, { onDelete: 'cascade' }).notNull(),
  tipoId: integer('tipo_id').references(() => lancamentoTipo.id, { onDelete: 'restrict' }).notNull(),
  numeroLancamento: varchar('numero_lancamento', { length: 50 }),
  data: date('data').notNull(),
  transmitenteId: integer('transmitente_id').references(() => pessoas.id, { onDelete: 'restrict' }),
  adquirenteId: integer('adquirente_id').references(() => pessoas.id, { onDelete: 'restrict' }),
  valorTransacao: decimal('valor_transacao', { precision: 10, scale: 2 }),
  area: decimal('area', { precision: 12, scale: 4 }),
  origem: varchar('origem', { length: 255 }),
  detalhes: text('detalhes'),
  observacoes: text('observacoes'),
  dataCadastro: date('data_cadastro').defaultNow().notNull(),
  forma: varchar('forma', { length: 100 }),
  descricao: text('descricao'),
  titulo: varchar('titulo', { length: 255 }),
  cartorioOrigemId: integer('cartorio_origem_id').references(() => cartorios.id, { onDelete: 'restrict' }),
  cartorioTransacaoId: integer('cartorio_transacao_id').references(() => cartorios.id, { onDelete: 'restrict' }),
  cartorioTransmissaoId: integer('cartorio_transmissao_id').references(() => cartorios.id, { onDelete: 'restrict' }),
  livroTransacao: varchar('livro_transacao', { length: 50 }),
  folhaTransacao: varchar('folha_transacao', { length: 50 }),
  dataTransacao: date('data_transacao'),
  livroOrigem: varchar('livro_origem', { length: 50 }),
  folhaOrigem: varchar('folha_origem', { length: 50 }),
  dataOrigem: date('data_origem'),
  ehInicioMatricula: boolean('eh_inicio_matricula').default(false).notNull(),
  documentoOrigemId: integer('documento_origem_id').references(() => documento.id, { onDelete: 'restrict' }),
}, (table) => [
  index('lancamento_id_idx').on(table.id),
]);

/**
 * Multiple people per transaction (many-to-many)
 */
export const lancamentoPessoa = pgTable('lancamentopessoa', {
  id: serial('id').primaryKey(),
  lancamentoId: integer('lancamento_id').references(() => lancamento.id, { onDelete: 'cascade' }).notNull(),
  pessoaId: integer('pessoa_id').references(() => pessoas.id, { onDelete: 'restrict' }).notNull(),
  tipo: tipoLancamentoPessoaEnum('tipo').notNull(),
  nomeDigitado: varchar('nome_digitado', { length: 255 }),
}, (table) => [
  unique('unique_lancamento_pessoa').on(table.lancamentoId, table.pessoaId, table.tipo),
]);

/**
 * Chain end tracking per origin
 */
export const origemFimCadeia = pgTable('origemfimcadeia', {
  id: serial('id').primaryKey(),
  lancamentoId: integer('lancamento_id').references(() => lancamento.id, { onDelete: 'cascade' }).notNull(),
  indiceOrigem: integer('indice_origem').notNull(),
  fimCadeia: boolean('fim_cadeia').default(false).notNull(),
  tipoFimCadeia: tipoFimCadeiaEnum('tipo_fim_cadeia'),
  especificacaoFimCadeia: text('especificacao_fim_cadeia'),
  classificacaoFimCadeia: classificacaoFimCadeiaEnum('classificacao_fim_cadeia'),
}, (table) => [
  unique('unique_origem_fim_cadeia').on(table.lancamentoId, table.indiceOrigem),
]);

/**
 * Chain end types (managed in admin)
 */
export const fimCadeia = pgTable('fimcadeia', {
  id: serial('id').primaryKey(),
  nome: varchar('nome', { length: 100 }).notNull().unique(),
  tipo: tipoFimCadeiaEnum('tipo').default('destacamento_publico').notNull(),
  classificacao: classificacaoFimCadeiaEnum('classificacao').default('origem_lidima').notNull(),
  sigla: varchar('sigla', { length: 50 }),
  descricao: text('descricao'),
  ativo: boolean('ativo').default(true).notNull(),
  dataCriacao: timestamp('data_criacao').defaultNow().notNull(),
  dataAtualizacao: timestamp('data_atualizacao').defaultNow().notNull(),
}, (table) => [
  index('fim_cadeia_nome_idx').on(table.nome),
]);

// =============================================================================
// TABLES - Alterações (Legacy - Not Actively Used)
// =============================================================================

/**
 * Alteration types (legacy)
 */
export const alteracoesTipo = pgTable('alteracoestipo', {
  id: serial('id').primaryKey(),
  tipo: tipoAlteracaoEnum('tipo').notNull(),
});

/**
 * Registration types (legacy)
 */
export const registroTipo = pgTable('registrotipo', {
  id: serial('id').primaryKey(),
  tipo: varchar('tipo', { length: 100 }).notNull(),
});

/**
 * Averbação types (legacy)
 */
export const averbacoesTipo = pgTable('averbacoestipo', {
  id: serial('id').primaryKey(),
  tipo: varchar('tipo', { length: 100 }).notNull(),
});

/**
 * Property alterations (legacy model)
 * Replaced by Lancamento system
 */
export const alteracoes = pgTable('alteracoes', {
  id: serial('id').primaryKey(),
  imovelId: integer('imovel_id').references(() => imovel.id, { onDelete: 'cascade' }).notNull(),
  tipoAlteracaoId: integer('tipo_alteracao_id').references(() => alteracoesTipo.id, { onDelete: 'cascade' }).notNull(),
  livro: varchar('livro', { length: 50 }),
  folha: varchar('folha', { length: 50 }),
  cartorioId: integer('cartorio_id').references(() => cartorios.id, { onDelete: 'cascade' }).notNull(),
  dataAlteracao: date('data_alteracao'),
  registroTipoId: integer('registro_tipo_id').references(() => registroTipo.id, { onDelete: 'cascade' }),
  averbacaoTipoId: integer('averbacao_tipo_id').references(() => averbacoesTipo.id, { onDelete: 'cascade' }),
  titulo: varchar('titulo', { length: 255 }),
  cartorioOrigemId: integer('cartorio_origem_id').references(() => cartorios.id, { onDelete: 'cascade' }).notNull(),
  livroOrigem: varchar('livro_origem', { length: 50 }),
  folhaOrigem: varchar('folha_origem', { length: 50 }),
  dataOrigem: date('data_origem'),
  transmitenteId: integer('transmitente_id').references(() => pessoas.id, { onDelete: 'cascade' }),
  adquirenteId: integer('adquirente_id').references(() => pessoas.id, { onDelete: 'cascade' }),
  valorTransacao: decimal('valor_transacao', { precision: 10, scale: 2 }),
  area: decimal('area', { precision: 12, scale: 4 }),
  observacoes: text('observacoes'),
  dataCadastro: date('data_cadastro').defaultNow().notNull(),
});

// =============================================================================
// RELATIONS
// =============================================================================

/**
 * Define relations for querying with Drizzle ORM
 * These relations enable type-safe joins and nested queries
 */
export const relations = defineRelations(
  {
    terraIndigenaReferencia,
    tis,
    pessoas,
    cartorios,
    importacaoCartorios,
    imovel,
    tisImovel,
    documentoTipo,
    documento,
    documentoImportado,
    lancamentoTipo,
    lancamento,
    lancamentoPessoa,
    origemFimCadeia,
    fimCadeia,
    alteracoesTipo,
    registroTipo,
    averbacoesTipo,
    alteracoes,
  },
  (r) => ({
    // Terra Indígena Referencia Relations
    terraIndigenaReferencia: {
      tis: r.many.tis(),
    },

    // TIs Relations
    tis: {
      terraReferencia: r.one.terraIndigenaReferencia({
        from: r.tis.terraReferenciaId,
        to: r.terraIndigenaReferencia.id,
        fields: ['nome', 'codigo', 'etnia', 'estado', 'area'],
      }),
      imoveis: r.many.imovel(),
      tisImoveis: r.many.tisImovel(),
    },

    // Pessoas Relations
    pessoas: {
      imoveisComoProprietario: r.many.imovel(),
      transmitenteLancamentos: r.many.lancamentoPessoa(),
      adquirenteLancamentos: r.many.lancamentoPessoa(),
    },

    // Cartórios Relations
    cartorios: {
      imoveis: r.many.imovel(),
      documentos: r.many.documento(),
      criAtualDocumentos: r.many.documento(),
      criOrigemDocumentos: r.many.documento(),
      cartorioOrigemLancamentos: r.many.lancamento(),
      cartorioTransacaoLancamentos: r.many.lancamento(),
      cartorioTransmissaoLancamentos: r.many.lancamento(),
      importacoes: r.many.importacaoCartorios(),
    },

    // Importação Cartórios Relations
    importacaoCartorios: {
      cartorio: r.many.cartorios(),
    },

    // Imovel Relations
    imovel: {
      terraIndigena: r.one.tis({
        from: r.imovel.terraIndigenaId,
        to: r.tis.id,
      }),
      proprietario: r.one.pessoas({
        from: r.imovel.proprietarioId,
        to: r.pessoas.id,
      }),
      cartorio: r.one.cartorios({
        from: r.imovel.cartorioId,
        to: r.cartorios.id,
      }),
      documentos: r.many.documento(),
      tisImoveis: r.many.tisImovel(),
      alteracoes: r.many.alteracoes(),
    },

    // TIs Imovel Relations (junction table)
    tisImovel: {
      tis: r.one.tis({
        from: r.tisImovel.tisCodigoId,
        to: r.tis.id,
      }),
      imovel: r.one.imovel({
        from: r.tisImovel.imovelId,
        to: r.imovel.id,
      }),
    },

    // Documento Tipo Relations
    documentoTipo: {
      documentos: r.many.documento(),
    },

    // Documento Relations
    documento: {
      imovel: r.one.imovel({
        from: r.documento.imovelId,
        to: r.imovel.id,
      }),
      tipo: r.one.documentoTipo({
        from: r.documento.tipoId,
        to: r.documentoTipo.id,
      }),
      cartorio: r.one.cartorios({
        from: r.documento.cartorioId,
        to: r.cartorios.id,
      }),
      criAtual: r.one.cartorios({
        from: r.documento.criAtualId,
        to: r.cartorios.id,
      }),
      criOrigem: r.one.cartorios({
        from: r.documento.criOrigemId,
        to: r.cartorios.id,
      }),
      lancamentos: r.many.lancamento(),
      lancamentosOrigem: r.many.lancamento(),
      documentoImportado: r.one.documentoImportado(),
    },

    // Documento Importado Relations
    documentoImportado: {
      documento: r.one.documento({
        from: r.documentoImportado.documentoId,
        to: r.documento.id,
      }),
      imovelOrigem: r.one.imovel({
        from: r.documentoImportado.imovelOrigemId,
        to: r.imovel.id,
      }),
    },

    // Lancamento Tipo Relations
    lancamentoTipo: {
      lancamentos: r.many.lancamento(),
    },

    // Lancamento Relations
    lancamento: {
      documento: r.one.documento({
        from: r.lancamento.documentoId,
        to: r.documento.id,
      }),
      tipo: r.one.lancamentoTipo({
        from: r.lancamento.tipoId,
        to: r.lancamentoTipo.id,
      }),
      transmitente: r.one.pessoas({
        from: r.lancamento.transmitenteId,
        to: r.pessoas.id,
      }),
      adquirente: r.one.pessoas({
        from: r.lancamento.adquirenteId,
        to: r.pessoas.id,
      }),
      cartorioOrigem: r.one.cartorios({
        from: r.lancamento.cartorioOrigemId,
        to: r.cartorios.id,
      }),
      cartorioTransacao: r.one.cartorios({
        from: r.lancamento.cartorioTransacaoId,
        to: r.cartorios.id,
      }),
      cartorioTransmissao: r.one.cartorios({
        from: r.lancamento.cartorioTransmissaoId,
        to: r.cartorios.id,
      }),
      documentoOrigem: r.one.documento({
        from: r.lancamento.documentoOrigemId,
        to: r.documento.id,
      }),
      pessoas: r.many.lancamentoPessoa(),
      origensFimCadeia: r.many.origemFimCadeia(),
    },

    // Lancamento Pessoa Relations
    lancamentoPessoa: {
      lancamento: r.one.lancamento({
        from: r.lancamentoPessoa.lancamentoId,
        to: r.lancamento.id,
      }),
      pessoa: r.one.pessoas({
        from: r.lancamentoPessoa.pessoaId,
        to: r.pessoas.id,
      }),
    },

    // Origem Fim Cadeia Relations
    origemFimCadeia: {
      lancamento: r.one.lancamento({
        from: r.origemFimCadeia.lancamentoId,
        to: r.lancamento.id,
      }),
    },

    // Fim Cadeia Relations
    fimCadeia: {
      // No direct relations - managed through UI
    },

    // Alteracoes Tipo Relations
    alteracoesTipo: {
      alteracoes: r.many.alteracoes(),
    },

    // Registro Tipo Relations
    registroTipo: {
      alteracoes: r.many.alteracoes(),
    },

    // Averbacoes Tipo Relations
    averbacoesTipo: {
      alteracoes: r.many.alteracoes(),
    },

    // Alteracoes Relations (Legacy)
    alteracoes: {
      imovel: r.one.imovel({
        from: r.alteracoes.imovelId,
        to: r.imovel.id,
      }),
      tipoAlteracao: r.one.alteracoesTipo({
        from: r.alteracoes.tipoAlteracaoId,
        to: r.alteracoesTipo.id,
      }),
      cartorio: r.one.cartorios({
        from: r.alteracoes.cartorioId,
        to: r.cartorios.id,
      }),
      registroTipo: r.one.registroTipo({
        from: r.alteracoes.registroTipoId,
        to: r.registroTipo.id,
      }),
      averbacaoTipo: r.one.averbacoesTipo({
        from: r.alteracoes.averbacaoTipoId,
        to: r.averbacoesTipo.id,
      }),
      cartorioOrigem: r.one.cartorios({
        from: r.alteracoes.cartorioOrigemId,
        to: r.cartorios.id,
      }),
      transmitente: r.one.pessoas({
        from: r.alteracoes.transmitenteId,
        to: r.pessoas.id,
      }),
      adquirente: r.one.pessoas({
        from: r.alteracoes.adquirenteId,
        to: r.pessoas.id,
      }),
    },
  })
);

// =============================================================================
// TYPE EXPORTS (for TypeScript usage)
// =============================================================================

export type TerraIndigenaReferencia = typeof terraIndigenaReferencia.$inferSelect;
export type TIs = typeof tis.$inferSelect;
export type Pessoas = typeof pessoas.$inferSelect;
export type Cartorios = typeof cartorios.$inferSelect;
export type ImportacaoCartorios = typeof importacaoCartorios.$inferSelect;
export type Imovel = typeof imovel.$inferSelect;
export type TisImovel = typeof tisImovel.$inferSelect;
export type DocumentoTipo = typeof documentoTipo.$inferSelect;
export type Documento = typeof documento.$inferSelect;
export type DocumentoImportado = typeof documentoImportado.$inferSelect;
export type LancamentoTipo = typeof lancamentoTipo.$inferSelect;
export type Lancamento = typeof lancamento.$inferSelect;
export type LancamentoPessoa = typeof lancamentoPessoa.$inferSelect;
export type OrigemFimCadeia = typeof origemFimCadeia.$inferSelect;
export type FimCadeia = typeof fimCadeia.$inferSelect;
export type AlteracoesTipo = typeof alteracoesTipo.$inferSelect;
export type RegistroTipo = typeof registroTipo.$inferSelect;
export type AverbacoesTipo = typeof averbacoesTipo.$inferSelect;
export type Alteracoes = typeof alteracoes.$inferSelect;

// =============================================================================
// UTILITY TYPES
// =============================================================================

export type NewTerraIndigenaReferencia = typeof terraIndigenaReferencia.$inferInsert;
export type NewTIs = typeof tis.$inferInsert;
export type NewPessoas = typeof pessoas.$inferInsert;
export type NewCartorios = typeof cartorios.$inferInsert;
export type NewImportacaoCartorios = typeof importacaoCartorios.$inferInsert;
export type NewImovel = typeof imovel.$inferInsert;
export type NewTisImovel = typeof tisImovel.$inferInsert;
export type NewDocumentoTipo = typeof documentoTipo.$inferInsert;
export type NewDocumento = typeof documento.$inferInsert;
export type NewDocumentoImportado = typeof documentoImportado.$inferInsert;
export type NewLancamentoTipo = typeof lancamentoTipo.$inferInsert;
export type NewLancamento = typeof lancamento.$inferInsert;
export type NewLancamentoPessoa = typeof lancamentoPessoa.$inferInsert;
export type NewOrigemFimCadeia = typeof origemFimCadeia.$inferInsert;
export type NewFimCadeia = typeof fimCadeia.$inferInsert;
export type NewAlteracoesTipo = typeof alteracoesTipo.$inferInsert;
export type NewRegistroTipo = typeof registroTipo.$inferInsert;
export type NewAverbacoesTipo = typeof averbacoesTipo.$inferInsert;
export type NewAlteracoes = typeof alteracoes.$inferInsert;
