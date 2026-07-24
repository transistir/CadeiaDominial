/**
 * PendenciaCartorio (Pending Cartório Queue) Schema
 *
 * When an origem references a document that cannot be automatically matched,
 * a pendencia_cartorio row is created to track the unresolved citation.
 * Human reviewers confirm or reject the suggested CRI/document match.
 *
 * Cross-CRI suggestions start as "fraca" confidence — matching across
 * different cartórios without explicit confirmation is weak by default.
 *
 * Auditable: who resolved and when, plus what was ultimately confirmed.
 */

import { sql } from "drizzle-orm";
import { integer, sqliteTable, text, check } from "drizzle-orm/sqlite-core";
import { origem } from "./origem";
import { cri } from "./cri";

export const pendenciaCartorio = sqliteTable(
  "pendencia_cartorio",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    origemId: integer("origem_id")
      .notNull()
      .references(() => origem.id, { onDelete: "cascade" }),
    criSugeridoId: integer("cri_sugerido_id").references(() => cri.id, {
      onDelete: "set null",
    }),
    confianca: text("confianca", {
      enum: ["fraca", "forte", "alerta"],
    }).notNull(),
    status: text("status", {
      enum: ["pendente", "confirmada", "rejeitada"],
    })
      .notNull()
      .default("pendente"),
    resolvidoPor: text("resolvido_por"),
    resolvidoEm: text("resolvido_em"),
    criConfirmadoId: integer("cri_confirmado_id").references(() => cri.id, {
      onDelete: "set null",
    }),
    createdAt: text("created_at").notNull(),
  },
  (table) => ({
    confiancaCheck: check(
      "pendencia_cartorio_confianca_check",
      sql`${table.confianca} IN ('fraca', 'forte', 'alerta')`
    ),
    statusCheck: check(
      "pendencia_cartorio_status_check",
      sql`${table.status} IN ('pendente', 'confirmada', 'rejeitada')`
    ),
  })
);

// Type exports
export type PendenciaCartorio = typeof pendenciaCartorio.$inferSelect;
export type NewPendenciaCartorio = typeof pendenciaCartorio.$inferInsert;
