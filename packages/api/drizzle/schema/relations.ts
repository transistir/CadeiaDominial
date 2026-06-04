/**
 * Drizzle ORM Relations — v2 schema
 *
 * Defines the relationship graph for Drizzle's relational query API
 * (`db.query.X.findMany({ with: { ... } })`).
 *
 * Mirrors the FK structure from `erd-v2.mmd`:
 *  - One-to-many: `many(targetTable)`
 *  - Many-to-one: `one(targetTable, { fields, references })`
 *  - One-to-one: `one(targetTable, { fields, references })` (no relationName needed)
 *
 * For FKs where the same target table is referenced multiple times via
 * different relations (e.g. `lancamento_move_event` has BOTH
 * `from_documento_id` and `to_documento_id` to `documento`), we use
 * `relationName` to disambiguate.
 */

import { relations } from "drizzle-orm";

import { cri } from "./cri";
import { user } from "./user";
import { pessoa } from "./pessoa";
import { imovel } from "./imovel";
import { imovelDocumento } from "./imovel_documento";
import { documento } from "./documento";
import { lancamentoTipo } from "./lancamento_tipo";
import { lancamento } from "./lancamento";
import { lancamentoPessoa } from "./lancamento_pessoa";
import { origem } from "./origem";
import { origemFimCadeia } from "./origem_fim_cadeia";
import { anotacaoVersao } from "./anotacao_versao";
import { lancamentoMoveEvent } from "./lancamento_move_event";
import { auditLog } from "./audit_log";
import { tis } from "./tis";
import { tisImovel } from "./tis_imovel";
import { terraIndigenaReferencia } from "./terra_indigena_referencia";

// =============================================================================
// CRI relations
// =============================================================================

export const criRelations = relations(cri, ({ many }) => ({
  documentos: many(documento),
  imoveis: many(imovel),
  origens: many(origem),
}));

// =============================================================================
// User relations (D3: researcher, distinct from pessoa)
// =============================================================================

export const userRelations = relations(user, ({ many }) => ({
  auditLogs: many(auditLog),
  movedEvents: many(lancamentoMoveEvent),
  anotacoesCriadas: many(anotacaoVersao, { relationName: "anotacao_created_by" }),
  anotacoesAutorOriginal: many(anotacaoVersao, { relationName: "anotacao_autor_original" }),
}));

// =============================================================================
// Pessoa relations (cartório domain entity)
// =============================================================================

export const pessoaRelations = relations(pessoa, ({ many }) => ({
  imoveis: many(imovel),
  lancamentoPessoas: many(lancamentoPessoa),
}));

// =============================================================================
// Imovel relations
// =============================================================================

export const imovelRelations = relations(imovel, ({ one, many }) => ({
  cri: one(cri, {
    fields: [imovel.criId],
    references: [cri.id],
  }),
  proprietario: one(pessoa, {
    fields: [imovel.proprietarioId],
    references: [pessoa.id],
  }),
  imovelDocumentos: many(imovelDocumento),
  tisImovel: many(tisImovel),
}));

// =============================================================================
// Documento relations
// =============================================================================

export const documentoRelations = relations(documento, ({ one, many }) => ({
  cri: one(cri, {
    fields: [documento.criId],
    references: [cri.id],
  }),
  imovelDocumentos: many(imovelDocumento),
  lancamentos: many(lancamento),
  origens: many(origem),
  moveEventsFrom: many(lancamentoMoveEvent, { relationName: "move_from" }),
  moveEventsTo: many(lancamentoMoveEvent, { relationName: "move_to" }),
}));

// =============================================================================
// ImovelDocumento (junction) relations
// =============================================================================

export const imovelDocumentoRelations = relations(imovelDocumento, ({ one, many }) => ({
  imovel: one(imovel, {
    fields: [imovelDocumento.imovelId],
    references: [imovel.id],
  }),
  documento: one(documento, {
    fields: [imovelDocumento.documentoId],
    references: [documento.id],
  }),
  anotacoes: many(anotacaoVersao),
}));

// =============================================================================
// LancamentoTipo relations
// =============================================================================

export const lancamentoTipoRelations = relations(lancamentoTipo, ({ many }) => ({
  lancamentos: many(lancamento),
}));

// =============================================================================
// Lancamento relations
// =============================================================================

export const lancamentoRelations = relations(lancamento, ({ one, many }) => ({
  documento: one(documento, {
    fields: [lancamento.documentoId],
    references: [documento.id],
  }),
  tipo: one(lancamentoTipo, {
    fields: [lancamento.tipoId],
    references: [lancamentoTipo.id],
  }),
  pessoas: many(lancamentoPessoa),
  origens: many(origem),
  moveEvents: many(lancamentoMoveEvent),
}));

// =============================================================================
// LancamentoPessoa (junction) relations
// =============================================================================

export const lancamentoPessoaRelations = relations(lancamentoPessoa, ({ one }) => ({
  lancamento: one(lancamento, {
    fields: [lancamentoPessoa.lancamentoId],
    references: [lancamento.id],
  }),
  pessoa: one(pessoa, {
    fields: [lancamentoPessoa.pessoaId],
    references: [pessoa.id],
  }),
}));

// =============================================================================
// Origem relations
// =============================================================================

export const origemRelations = relations(origem, ({ one }) => ({
  lancamento: one(lancamento, {
    fields: [origem.lancamentoId],
    references: [lancamento.id],
  }),
  cri: one(cri, {
    fields: [origem.criId],
    references: [cri.id],
  }),
  documento: one(documento, {
    fields: [origem.documentoId],
    references: [documento.id],
  }),
  fimCadeia: one(origemFimCadeia, {
    fields: [origem.id],
    references: [origemFimCadeia.origemId],
  }),
}));

// =============================================================================
// OrigemFimCadeia relations (1:1 with Origem)
// =============================================================================

export const origemFimCadeiaRelations = relations(origemFimCadeia, ({ one }) => ({
  origem: one(origem, {
    fields: [origemFimCadeia.origemId],
    references: [origem.id],
  }),
}));

// =============================================================================
// AnotacaoVersao relations
// =============================================================================

export const anotacaoVersaoRelations = relations(anotacaoVersao, ({ one }) => ({
  imovelDocumento: one(imovelDocumento, {
    fields: [anotacaoVersao.imovelDocumentoId],
    references: [imovelDocumento.id],
  }),
  autorOriginal: one(user, {
    fields: [anotacaoVersao.autorOriginalId],
    references: [user.id],
    relationName: "anotacao_autor_original",
  }),
  createdBy: one(user, {
    fields: [anotacaoVersao.createdById],
    references: [user.id],
    relationName: "anotacao_created_by",
  }),
}));

// =============================================================================
// LancamentoMoveEvent relations
// =============================================================================

export const lancamentoMoveEventRelations = relations(lancamentoMoveEvent, ({ one }) => ({
  lancamento: one(lancamento, {
    fields: [lancamentoMoveEvent.lancamentoId],
    references: [lancamento.id],
  }),
  fromDocumento: one(documento, {
    fields: [lancamentoMoveEvent.fromDocumentoId],
    references: [documento.id],
    relationName: "move_from",
  }),
  toDocumento: one(documento, {
    fields: [lancamentoMoveEvent.toDocumentoId],
    references: [documento.id],
    relationName: "move_to",
  }),
  movedBy: one(user, {
    fields: [lancamentoMoveEvent.movedById],
    references: [user.id],
  }),
}));

// =============================================================================
// AuditLog relations
// =============================================================================

export const auditLogRelations = relations(auditLog, ({ one, many }) => ({
  actor: one(user, {
    fields: [auditLog.actorId],
    references: [user.id],
  }),
  moveEvents: many(lancamentoMoveEvent),
}));

// =============================================================================
// Tis relations
// =============================================================================

export const tisRelations = relations(tis, ({ one, many }) => ({
  terraReferencia: one(terraIndigenaReferencia, {
    fields: [tis.terraReferenciaId],
    references: [terraIndigenaReferencia.id],
  }),
  tisImovel: many(tisImovel),
}));

// =============================================================================
// TisImovel (junction) relations
// =============================================================================

export const tisImovelRelations = relations(tisImovel, ({ one }) => ({
  tis: one(tis, {
    fields: [tisImovel.tisId],
    references: [tis.id],
  }),
  imovel: one(imovel, {
    fields: [tisImovel.imovelId],
    references: [imovel.id],
  }),
}));

// =============================================================================
// TerraIndigenaReferencia relations
// =============================================================================

export const terraIndigenaReferenciaRelations = relations(terraIndigenaReferencia, ({ many }) => ({
  tis: many(tis),
}));
