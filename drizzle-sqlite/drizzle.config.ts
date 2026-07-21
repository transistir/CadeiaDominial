/**
 * Drizzle Kit Configuration - SQLite Version
 *
 * This configuration file is used by drizzle-kit for migrations and introspection.
 *
 * Commands:
 * - `npx drizzle-kit generate` - Generate SQL migrations from schema changes
 * - `npx drizzle-kit push` - Push schema directly to database (development)
 * - `npx drizzle-kit introspect` - Generate schema from existing database
 * - `npx drizzle-kit studio` - Open Drizzle Studio to browse database
 */

import type { Config } from 'drizzle-kit';

export default {
  // Schema files location
  schema: './drizzle-sqlite/schema/index.ts',

  // Output directory for generated migrations
  out: './drizzle-sqlite/migrations',

  // Database driver
  dialect: 'sqlite',

  // Database connection
  dbCredentials: {
    url: process.env.SQLITE_DB_PATH || './db.sqlite3',
  },

  // Verbose output during migrations
  verbose: true,

  // Strict mode - fail on warnings
  strict: true,
} satisfies Config;
