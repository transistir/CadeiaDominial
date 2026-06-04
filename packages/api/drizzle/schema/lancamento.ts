/**
 * Lancamento (transaction / recording) Schema
 *
 * Q7b=B: Lancamentos are EVIDÊNCIA — they survive soft-delete of their
 * parent Imovel/Document as orphans. `documento_id` is ON DELETE SET NULL
 * so that, if the parent Documento is admin-hard-deleted, the Lancamento
 * row remains with documento_id=NULL.
 *
 * Q11b: NO `cri_origem_id` column. The CRI of an origin is captured by
 * `origem.cri_id` (the Origem of the Lancamento already has its own
 * `cri_id` FK). Lancamento inherits this transitively.
 *
 * Q11b: `cartorio_transmissao_nome` is FREE-FORM TEXT (no FK). Tabelionato
 * de notas can be any cartório; we don't model them in v2.
 *
 * Q14=B: Lancamento is NEVER mutated by MOVE. The MOVE operation is
 * recorded in `lancamento_move_event` (append-only). The `documento_id`
 * column reflects the ORIGINAL chain attachment, not the current location.
 * The current location is computed by the `v_lancamento_current_location`
 * view (see `views.ts`).
 *
 * Q14=invariante (write-time, in app): before creating a
 * `lancamento_move_event`, validate that `from_documento_id` matches
 * `v_lancamento_current_location.current_documento_id` for that Lancamento.
 * See docs/db/SCHEMA_DECISOES_PENDENTES.md (Q14 implementation).
 *
 * UNIQUE (documento_id, numero_lancamento): per-document Lancamento
 * numbering. `numero_lancamento` can be NULL during migration.
 *
 * T3: `valor_transacao` in centavos (integer); `area` in centiares
 * (1 are = 100 m² → centiares = m²).
 *
 * F3: F1, F2, F3 (Codex round 2): explicit CHECKs on enums are added in
 * the migration (Drizzle `enum` is TS-only).
 */

import { sql } from "drizzle-orm";
import {
  integer,
  sqliteTable,
  text,
  uniqueIndex,
  check,
} from "drizzle-orm/sqlite-core";
import { documento } from "./documento";
import { lancamentoTipo } from "./lancamento_tipo";
import { auditLog } from "./audit_log";

export const lancamento = sqliteTable(
  "lancamento",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    /** Partial date per T3. */
    data: text("data"),
    /** Centavos (integer) — avoid real precision loss. */
    valorTransacao: integer("valor_transacao_centavos"),
    /** Centiares (1 are = 100 m²). */
    area: integer("area_centiares"),
    detalhes: text("detalhes"),
    observacoes: text("observacoes"),
    dataCadastro: text("data_cadastro"),
    /**
     * Q7b=B: SET NULL on documento delete — Lancamento preserved órfão.
     * Q14=B: this is the ORIGINAL chain attachment, not current location.
     */
    documentoId: integer("documento_id").references(() => documento.id, {
      onDelete: "set null",
    }),
    /** RESTRICT — can't remove a type in use; migrate Lancamentos first. */
    tipoId: integer("tipo_id")
      .notNull()
      .references(() => lancamentoTipo.id, { onDelete: "restrict" }),
    descricao: text("descricao"),
    forma: text("forma"),
    titulo: text("titulo"),
    /**
     * CHECK (numero_lancamento > 0) WHERE NOT NULL — enforced in migration.
     * NULL allowed during migration / before assignment.
     */
    numeroLancamento: integer("numero_lancamento"),
    /** Q11b: FREE-FORM TEXT. NO FK. */
    cartorioTransmissaoNome: text("cartorio_transmissao_nome"),
    livroTransmissao: text("livro_transmissao"),
    folhaTransmissao: text("folha_transmissao"),
    dataTransmissao: text("data_transmissao"),
    createdAt: text("created_at")
      .notNull(),
    /** Q2=B: soft-delete (L preserved órfão per Q7b=B). */
    deletedAt: text("deleted_at"),
    /** Q9+C: provenance of the soft-delete. SET NULL if audit purged. */
    deleteOperationId: integer("delete_operation_id").references(
      () => auditLog.id,
      { onDelete: "set null" }
    ),
  },
  (table) => ({
    /**
     * Per-document Lancamento numbering. NULL numero_lancamento is allowed
     * during migration; uniqueness applies only when the column is non-null.
     */
    documentoNumeroLancamentoUnique: uniqueIndex(
      "uq_lancamento_documento_numero"
    )
      .on(table.documentoId, table.numeroLancamento)
      .where(sql`${table.numeroLancamento} IS NOT NULL`),
    /** CHECK (numero_lancamento > 0) WHERE NOT NULL — partial CHECK. */
    numeroLancamentoPositivo: check(
      "lancamento_numero_lancamento_positivo",
      sql`${table.numeroLancamento} IS NULL OR ${table.numeroLancamento} > 0`
    ),
  })
);

// Type exports
export type Lancamento = typeof lancamento.$inferSelect;
export type NewLancamento = typeof lancamento.$inferInsert;
