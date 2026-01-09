/**
 * Drizzle Database Client
 *
 * This file provides the database connection and query client for the application.
 * Import this file to access the database in your application code.
 *
 * Usage:
 * ```ts
 * import { db } from './drizzle/db';
 * import { pessoas, imovel } from './drizzle/schema';
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
 */

import { drizzle } from 'drizzle-orm/node-postgres';
import { Pool } from 'pg';
import * as schema from './schema';

/**
 * Create PostgreSQL connection pool
 *
 * ⚠️ SECURITY WARNING: The default values below are for LOCAL DEVELOPMENT ONLY.
 * In production, ALL connection parameters MUST be provided via environment variables:
 *   - DB_HOST: Database server hostname
 *   - DB_PORT: Database server port
 *   - DB_USER: Database username (never use 'postgres' superuser in production)
 *   - DB_PASSWORD: Database password (required in production)
 *   - DB_NAME: Database name
 *
 * Consider using a secrets manager (AWS Secrets Manager, HashiCorp Vault, etc.)
 * for production credentials.
 */
const pool = new Pool({
  host: process.env.DB_HOST || 'localhost',
  port: Number(process.env.DB_PORT) || 5432,
  user: process.env.DB_USER || 'postgres',
  password: process.env.DB_PASSWORD || '',
  database: process.env.DB_NAME || 'cadeia_dominial',
  max: 20,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});

// Create Drizzle database instance with schema for relational queries
export const db = drizzle(pool, { schema });

// Export pool for manual connection management if needed
export { pool };

// Type exports for convenience
export type DB = typeof db;
