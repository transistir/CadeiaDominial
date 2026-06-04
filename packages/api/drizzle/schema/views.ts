/**
 * SQLite Views (D1-compatible) for the v2 schema.
 *
 * T2: `v_lancamento_current_location` — "where is this Lancamento NOW?"
 *
 * The MOVE operation is event-sourced (Q14=B): the Lancamento row is
 * never mutated. To find the current chain attachment, query the latest
 * `lancamento_move_event` for the Lancamento (or its original
 * `documento_id` if no MOVE has occurred).
 *
 * The view also filters out soft-deleted Lancamentos AND soft-deleted
 * Documentos at the destination (R3-4 / round 3 MUST-FIX: filtering
 * `documento.deleted_at` is critical — without it, the view could show
 * a Lancamento as "in" a soft-deleted Documento, hiding the removal).
 *
 * Edge case (Opus 4.8 flag, intentional): if the current destination
 * Documento is soft-deleted, the Lancamento disappears from this view
 * — there's no fallback to a previous move event. This is by design
 * (Q15=D4): soft-delete of a Documento is admin-only and intentional.
 * The UI must detect "Lancamento missing from chain" and surface
 * "Documento in removal — see admin".
 *
 * T3: `v_documento_orfao` — "which Documentos are in NO active chain?"
 *
 * A Documento is "orphan" when it has no active (deleted_at IS NULL)
 * `imovel_documento` junction. State-derived (Q15=D4): no `is_orfao`
 * column, always correct via this view.
 *
 * Both views are D1-compatible (SQLite CREATE VIEW is fully supported).
 */

import { sql } from "drizzle-orm";
import { integer, sqliteView, text } from "drizzle-orm/sqlite-core";

/**
 * T2: current chain location of a Lancamento.
 * Filters: l.deleted_at IS NULL AND d.deleted_at IS NULL.
 */
export const vLancamentoCurrentLocation = sqliteView(
  "v_lancamento_current_location",
  {
    lancamentoId: integer("lancamento_id").notNull(),
    // Nullable: a NULL `currentDocumentoId` means the lancamento is "preso"
    // (latest `lancamento_move_event.to_documento_id` was hard-deleted or
    // never set), so the view reports "no current location" and the row is
    // omitted by the INNER JOIN on `documento` below. Distinct from
    // "no move event row exists" — that case falls back to `l.documento_id`.
    currentDocumentoId: integer("current_documento_id"),
  }
).as(sql`
  SELECT
    inner_q.lancamento_id AS lancamento_id,
    inner_q.current_documento_id AS current_documento_id
  FROM (
    SELECT
      l.id AS lancamento_id,
      CASE
        WHEN latest.lancamento_id IS NULL THEN l.documento_id
        ELSE latest.to_documento_id
      END AS current_documento_id
    FROM lancamento l
    LEFT JOIN (
      SELECT me.lancamento_id, me.to_documento_id
      FROM lancamento_move_event me
      WHERE me.id = (
        SELECT me2.id
        FROM lancamento_move_event me2
        WHERE me2.lancamento_id = me.lancamento_id
        ORDER BY me2.moved_at DESC, me2.id DESC
        LIMIT 1
      )
    ) latest ON latest.lancamento_id = l.id
    WHERE l.deleted_at IS NULL
  ) inner_q
  INNER JOIN documento d ON d.id = inner_q.current_documento_id
  WHERE d.deleted_at IS NULL
`);

/**
 * T3: Documentos not in any active chain.
 */
export const vDocumentoOrfao = sqliteView("v_documento_orfao", {
  id: integer("id").notNull(),
  tipo: text("tipo").notNull(),
  numero: text("numero").notNull(),
  criId: integer("cri_id").notNull(),
}).as(sql`
  SELECT d.id, d.tipo, d.numero, d.cri_id
  FROM documento d
  WHERE d.deleted_at IS NULL
    AND NOT EXISTS (
      SELECT 1 FROM imovel_documento id_
      WHERE id_.documento_id = d.id
        AND id_.deleted_at IS NULL
    )
`);

// Type exports
export type VLancamentoCurrentLocation = typeof vLancamentoCurrentLocation.$inferSelect;
export type VDocumentoOrfao = typeof vDocumentoOrfao.$inferSelect;
