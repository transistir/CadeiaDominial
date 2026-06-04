/**
 * Drizzle v2 Schema — index re-exports
 *
 * Re-exports all v2 tables, relations, and views from a single entry point
 * for use by Drizzle Kit (`schema: "./drizzle/schema/index.ts"` in the
 * future) and by the application code (e.g. `import { imovel } from
 * "./drizzle/schema"`).
 *
 * Until `drizzle.config.ts` is updated to point at this directory, the
 * legacy `schema.ts` re-exports the same surface.
 */

export * from "./cri";
export * from "./user";
export * from "./pessoa";
export * from "./imovel";
export * from "./imovel_documento";
export * from "./documento";
export * from "./lancamento_tipo";
export * from "./lancamento";
export * from "./lancamento_pessoa";
export * from "./origem";
export * from "./origem_fim_cadeia";
export * from "./anotacao_versao";
export * from "./lancamento_move_event";
export * from "./audit_log";
export * from "./tis";
export * from "./tis_imovel";
export * from "./terra_indigena_referencia";

export * from "./relations";
export * from "./views";
