/**
 * People/Persons Schema
 */

import { pgTable, serial, varchar, date } from 'drizzle-orm/pg-core';

/**
 * Natural or legal persons involved in property transactions
 */
export const pessoas = pgTable('dominial_pessoas', {
  id: serial('id').primaryKey(),
  nome: varchar('nome', { length: 255 }).notNull(),
  cpf: varchar('cpf', { length: 11 }).unique(),
  rg: varchar('rg', { length: 20 }),
  dataNascimento: date('data_nascimento'),
  email: varchar('email', { length: 254 }),
  telefone: varchar('telefone', { length: 15 }),
});

// Type exports
export type Pessoa = typeof pessoas.$inferSelect;
export type NewPessoa = typeof pessoas.$inferInsert;
