/**
 * People/Persons Schema - SQLite Version
 *
 * SQLite Compatibility Notes:
 * - Uses `text` instead of `varchar` (SQLite doesn't enforce length limits)
 * - Uses `integer().primaryKey({ autoIncrement: true })` instead of `serial`
 */

import { sqliteTable, text, integer } from 'drizzle-orm/sqlite-core';

/**
 * Natural or legal persons involved in property transactions
 */
export const pessoas = sqliteTable('dominial_pessoas', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  nome: text('nome').notNull(),
  cpf: text('cpf').unique(), // Brazilian tax ID (11 chars)
  rg: text('rg'), // ID document
  dataNascimento: text('data_nascimento'), // DATE as ISO string (YYYY-MM-DD)
  email: text('email'),
  telefone: text('telefone'),
});

// Type exports
export type Pessoa = typeof pessoas.$inferSelect;
export type NewPessoa = typeof pessoas.$inferInsert;
