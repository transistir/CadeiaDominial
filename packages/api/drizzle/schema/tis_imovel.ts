/**
 * TisImovel (TI ↔ Imovel junction) Schema
 *
 * Many-to-many between Indigenous Land records and Properties. Indicates
 * which Imóveis are inside (or disputed with) which TIs.
 *
 * No soft-delete (Q2: TIs/Imoveis already have their own soft-delete;
 * the junction follows via CASCADE). The junction row disappears when
 * either side is hard-deleted.
 *
 * UNIQUE (tis_id, imovel_id) per ERD.
 *
 * CASCADE on both sides — junction is fully dependent.
 */

import { integer, sqliteTable, text, uniqueIndex } from "drizzle-orm/sqlite-core";
import { tis } from "./tis";
import { imovel } from "./imovel";

export const tisImovel = sqliteTable(
  "tis_imovel",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    tisId: integer("tis_id")
      .notNull()
      .references(() => tis.id, { onDelete: "cascade" }),
    imovelId: integer("imovel_id")
      .notNull()
      .references(() => imovel.id, { onDelete: "cascade" }),
    createdAt: text("created_at")
      .notNull(),
  },
  (table) => ({
    /** UNIQUE (tis_id, imovel_id) per ERD. */
    tisImovelUnique: uniqueIndex("uq_tis_imovel_tis_imovel").on(
      table.tisId,
      table.imovelId
    ),
  })
);

// Type exports
export type TisImovel = typeof tisImovel.$inferSelect;
export type NewTisImovel = typeof tisImovel.$inferInsert;
