/**
 * Drizzle ORM Relations
 *
 * Defines the relationships between tables for query building and type inference.
 */

import { relations } from 'drizzle-orm';
import { terraIndigenaReferencia, tis } from './tis';
import { pessoas } from './pessoas';
import { cartorios, importacaoCartorios } from './cartorios';
import { imovel, tisImovel } from './imovel';
import { documentoTipo, documento, documentoImportado } from './documentos';
import {
  lancamentoTipo,
  lancamento,
  lancamentoPessoa,
  origemFimCadeia,
  fimCadeia,
} from './lancamentos';
import {
  alteracoesTipo,
  registroTipo,
  averbacoesTipo,
  alteracoes,
} from './alteracoes';

// ============================================================================
// Terra Indigena Relations
// ============================================================================

export const terraIndigenaReferenciaRelations = relations(
  terraIndigenaReferencia,
  ({ many }) => ({
    tis: many(tis),
  })
);

export const tisRelations = relations(tis, ({ one, many }) => ({
  terraReferencia: one(terraIndigenaReferencia, {
    fields: [tis.terraReferenciaId],
    references: [terraIndigenaReferencia.id],
  }),
  imoveis: many(imovel),
  tisImovel: many(tisImovel),
}));

// ============================================================================
// Pessoas Relations
// ============================================================================

export const pessoasRelations = relations(pessoas, ({ many }) => ({
  imoveisProprietario: many(imovel),
  lancamentosTransmitente: many(lancamento, { relationName: 'transmitente' }),
  lancamentosAdquirente: many(lancamento, { relationName: 'adquirente' }),
  lancamentoPessoas: many(lancamentoPessoa),
  alteracoesTransmitente: many(alteracoes, { relationName: 'alteracaoTransmitente' }),
  alteracoesAdquirente: many(alteracoes, { relationName: 'alteracaoAdquirente' }),
}));

// ============================================================================
// Cartorios Relations
// ============================================================================

export const cartoriosRelations = relations(cartorios, ({ many }) => ({
  imoveis: many(imovel),
  documentos: many(documento, { relationName: 'documentoCartorio' }),
  documentosCriAtual: many(documento, { relationName: 'documentoCriAtual' }),
  documentosCriOrigem: many(documento, { relationName: 'documentoCriOrigem' }),
  lancamentosOrigem: many(lancamento, { relationName: 'lancamentoCartorioOrigem' }),
  lancamentosTransacao: many(lancamento, { relationName: 'lancamentoCartorioTransacao' }),
  lancamentosTransmissao: many(lancamento, {
    relationName: 'lancamentoCartorioTransmissao',
  }),
  alteracoes: many(alteracoes, { relationName: 'alteracaoCartorio' }),
  alteracoesOrigem: many(alteracoes, { relationName: 'alteracaoCartorioOrigem' }),
}));

// ============================================================================
// Imovel Relations
// ============================================================================

export const imovelRelations = relations(imovel, ({ one, many }) => ({
  terraIndigena: one(tis, {
    fields: [imovel.terraIndigenaIdId],
    references: [tis.id],
  }),
  proprietario: one(pessoas, {
    fields: [imovel.proprietarioId],
    references: [pessoas.id],
  }),
  cartorio: one(cartorios, {
    fields: [imovel.cartorioId],
    references: [cartorios.id],
  }),
  documentos: many(documento),
  tisImovel: many(tisImovel),
  documentosImportados: many(documentoImportado),
  alteracoes: many(alteracoes),
}));

export const tisImovelRelations = relations(tisImovel, ({ one }) => ({
  tis: one(tis, {
    fields: [tisImovel.tisCodigoId],
    references: [tis.id],
  }),
  imovel: one(imovel, {
    fields: [tisImovel.imovelId],
    references: [imovel.id],
  }),
}));

// ============================================================================
// Documento Relations
// ============================================================================

export const documentoTipoRelations = relations(documentoTipo, ({ many }) => ({
  documentos: many(documento),
}));

export const documentoRelations = relations(documento, ({ one, many }) => ({
  imovel: one(imovel, {
    fields: [documento.imovelId],
    references: [imovel.id],
  }),
  tipo: one(documentoTipo, {
    fields: [documento.tipoId],
    references: [documentoTipo.id],
  }),
  cartorio: one(cartorios, {
    fields: [documento.cartorioId],
    references: [cartorios.id],
    relationName: 'documentoCartorio',
  }),
  criAtual: one(cartorios, {
    fields: [documento.criAtualId],
    references: [cartorios.id],
    relationName: 'documentoCriAtual',
  }),
  criOrigem: one(cartorios, {
    fields: [documento.criOrigemId],
    references: [cartorios.id],
    relationName: 'documentoCriOrigem',
  }),
  lancamentos: many(lancamento),
  lancamentosOrigem: many(lancamento, { relationName: 'lancamentoDocumentoOrigem' }),
  documentosImportados: many(documentoImportado),
}));

export const documentoImportadoRelations = relations(documentoImportado, ({ one }) => ({
  documento: one(documento, {
    fields: [documentoImportado.documentoId],
    references: [documento.id],
  }),
  imovelOrigem: one(imovel, {
    fields: [documentoImportado.imovelOrigemId],
    references: [imovel.id],
  }),
}));

// ============================================================================
// Lancamento Relations
// ============================================================================

export const lancamentoTipoRelations = relations(lancamentoTipo, ({ many }) => ({
  lancamentos: many(lancamento),
}));

export const lancamentoRelations = relations(lancamento, ({ one, many }) => ({
  documento: one(documento, {
    fields: [lancamento.documentoId],
    references: [documento.id],
  }),
  tipo: one(lancamentoTipo, {
    fields: [lancamento.tipoId],
    references: [lancamentoTipo.id],
  }),
  transmitente: one(pessoas, {
    fields: [lancamento.transmitenteId],
    references: [pessoas.id],
    relationName: 'transmitente',
  }),
  adquirente: one(pessoas, {
    fields: [lancamento.adquirenteId],
    references: [pessoas.id],
    relationName: 'adquirente',
  }),
  cartorioOrigem: one(cartorios, {
    fields: [lancamento.cartorioOrigemId],
    references: [cartorios.id],
    relationName: 'lancamentoCartorioOrigem',
  }),
  cartorioTransacao: one(cartorios, {
    fields: [lancamento.cartorioTransacaoId],
    references: [cartorios.id],
    relationName: 'lancamentoCartorioTransacao',
  }),
  cartorioTransmissao: one(cartorios, {
    fields: [lancamento.cartorioTransmissaoId],
    references: [cartorios.id],
    relationName: 'lancamentoCartorioTransmissao',
  }),
  documentoOrigem: one(documento, {
    fields: [lancamento.documentoOrigemId],
    references: [documento.id],
    relationName: 'lancamentoDocumentoOrigem',
  }),
  pessoas: many(lancamentoPessoa),
  origensFimCadeia: many(origemFimCadeia),
}));

export const lancamentoPessoaRelations = relations(lancamentoPessoa, ({ one }) => ({
  lancamento: one(lancamento, {
    fields: [lancamentoPessoa.lancamentoId],
    references: [lancamento.id],
  }),
  pessoa: one(pessoas, {
    fields: [lancamentoPessoa.pessoaId],
    references: [pessoas.id],
  }),
}));

export const origemFimCadeiaRelations = relations(origemFimCadeia, ({ one }) => ({
  lancamento: one(lancamento, {
    fields: [origemFimCadeia.lancamentoId],
    references: [lancamento.id],
  }),
}));

// ============================================================================
// Alteracoes Relations
// ============================================================================

export const alteracoesTipoRelations = relations(alteracoesTipo, ({ many }) => ({
  alteracoes: many(alteracoes),
}));

export const registroTipoRelations = relations(registroTipo, ({ many }) => ({
  alteracoes: many(alteracoes),
}));

export const averbacoesTipoRelations = relations(averbacoesTipo, ({ many }) => ({
  alteracoes: many(alteracoes),
}));

export const alteracoesRelations = relations(alteracoes, ({ one }) => ({
  imovel: one(imovel, {
    fields: [alteracoes.imovelIdId],
    references: [imovel.id],
  }),
  tipoAlteracao: one(alteracoesTipo, {
    fields: [alteracoes.tipoAlteracaoIdId],
    references: [alteracoesTipo.id],
  }),
  cartorio: one(cartorios, {
    fields: [alteracoes.cartorioId],
    references: [cartorios.id],
    relationName: 'alteracaoCartorio',
  }),
  cartorioOrigem: one(cartorios, {
    fields: [alteracoes.cartorioOrigemId],
    references: [cartorios.id],
    relationName: 'alteracaoCartorioOrigem',
  }),
  registroTipo: one(registroTipo, {
    fields: [alteracoes.registroTipoId],
    references: [registroTipo.id],
  }),
  averbacaoTipo: one(averbacoesTipo, {
    fields: [alteracoes.averbacaoTipoId],
    references: [averbacoesTipo.id],
  }),
  transmitente: one(pessoas, {
    fields: [alteracoes.transmitenteId],
    references: [pessoas.id],
    relationName: 'alteracaoTransmitente',
  }),
  adquirente: one(pessoas, {
    fields: [alteracoes.adquirenteId],
    references: [pessoas.id],
    relationName: 'alteracaoAdquirente',
  }),
}));
