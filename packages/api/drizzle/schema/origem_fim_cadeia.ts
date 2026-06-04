/**
 * OrigemFimCadeia (end-of-chain details for an Origem) Schema
 *
 * Q3=B: an Origem can be the "end of chain" (no further document is
 * traceable). When `origem.tipo = 'fim_cadeia'`, this table captures
 * the details: why the chain ended, classification, public-patrimony
 * sigla, etc.
 *
 * 1:1 with Origem: each Origem has 0..1 OrigemFimCadeia. Enforced by
 * UNIQUE INDEX on `origem_id` (a partial UNIQUE excluding NULL).
 *
 * ON DELETE CASCADE: if the Origem is hard-deleted (admin-only), its
 * OrigemFimCadeia follows. (Origens in normal flow are never hard-deleted.)
 *
 * Fields:
 *  - `tipo_fim_cadeia`: 'destacamento_publico' | 'sem_origem' | 'outra' | ...
 *  - `classificacao_fim_cadeia`: REQUIRED when tipo_fim_cadeia is set
 *  - `especificacao_fim_cadeia`: REQUIRED when tipo_fim_cadeia = 'outra'
 *  - `sigla_patrimonio_publico`: REQUIRED when tipo_fim_cadeia = 'destacamento_publico'
 */

import { integer, sqliteTable, text } from "drizzle-orm/sqlite-core";
import { origem } from "./origem";

export const origemFimCadeia = sqliteTable(
  "origem_fim_cadeia",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    /**
     * UNIQUE 1:1 with origem. CASCADE on origem delete.
     */
    origemId: integer("origem_id")
      .notNull()
      .unique()
      .references(() => origem.id, { onDelete: "cascade" }),
    /**
     * 'destacamento_publico' | 'sem_origem' | 'outra' | ... —
     * CHECK in migration. No Drizzle `enum` because the list is
     * domain-extensible.
     */
    tipoFimCadeia: text("tipo_fim_cadeia"),
    /** Required when tipo_fim_cadeia is set. */
    classificacaoFimCadeia: text("classificacao_fim_cadeia"),
    /** Required when tipo_fim_cadeia = 'outra'. */
    especificacaoFimCadeia: text("especificacao_fim_cadeia"),
    /** Required when tipo_fim_cadeia = 'destacamento_publico'. */
    siglaPatrimonioPublico: text("sigla_patrimonio_publico"),
  },
  (table) => ({
    // The 1:1 UNIQUE on origem_id is enforced by the column-level
    // `.unique()` above; no separate index needed here.
  })
);

// Type exports
export type OrigemFimCadeia = typeof origemFimCadeia.$inferSelect;
export type NewOrigemFimCadeia = typeof origemFimCadeia.$inferInsert;
