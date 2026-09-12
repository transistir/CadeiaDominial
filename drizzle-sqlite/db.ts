/**
 * Drizzle Database Client - SQLite Version
 *
 * This file provides the database connection and query client for SQLite.
 * Import this file to access the database in your application code.
 *
 * Usage:
 * ```ts
 * import { db } from './drizzle-sqlite/db';
 * import { pessoas, imovel } from './drizzle-sqlite/schema';
 *
 * // Simple query
 * const allPessoas = await db.select().from(pessoas);
 *
 * // Query with relations
 * const imoveisWithOwners = await db.query.imovel.findMany({
 *   with: {
 *     proprietario: true,
 *     cartorio: true,
 *   },
 * });
 * ```
 *
 * SQLite-specific notes:
 * - Foreign keys must be enabled explicitly via PRAGMA
 * - Uses better-sqlite3 for synchronous operations (faster)
 * - File-based database, no server required
 */

import { drizzle } from 'drizzle-orm/better-sqlite3';
import Database from 'better-sqlite3';
import * as schema from './schema';

/**
 * SQLite database file path
 *
 * For development, uses a local file. In production, configure via environment variable.
 * The ':memory:' option creates an in-memory database (useful for testing).
 */
const dbPath = process.env.SQLITE_DB_PATH || './db.sqlite3';

/**
 * Create SQLite database connection
 *
 * Note: For Django compatibility, this should point to the same database file
 * that Django uses (typically 'db.sqlite3' in the project root).
 */
const sqlite = new Database(dbPath);

// Enable foreign key constraints (SQLite has them disabled by default)
sqlite.pragma('foreign_keys = ON');

// Enable WAL mode for better concurrent read performance
sqlite.pragma('journal_mode = WAL');

// Create Drizzle database instance with schema for relational queries
export const db = drizzle(sqlite, { schema });

// Export the raw SQLite connection for advanced operations
export { sqlite };

// Type exports for convenience
export type DB = typeof db;
