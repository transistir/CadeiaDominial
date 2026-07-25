/**
 * Database factory for the seed package.
 *
 * Creates a Drizzle ORM instance backed by better-sqlite3, with the v2 schema
 * wired in and migrations applied. This keeps better-sqlite3 out of the
 * Workers build (packages/api/src) while giving typed insert/returning in
 * the seed CLI.
 *
 * Usage:
 *   ```ts
 *   import { createSeedDatabase } from "./db.js";
 *   const db = createSeedDatabase(":memory:");
 *   await migrate(db, { migrationsFolder: "../packages/api/drizzle/migrations" });
 *   ```
 */

import Database from "better-sqlite3";
import { drizzle } from "drizzle-orm/better-sqlite3";
import * as schema from "../../packages/api/drizzle/schema/index.js";
import { migrate } from "drizzle-orm/better-sqlite3/migrator";
import path from "path";
import { fileURLToPath } from "url";

const _filename = fileURLToPath(import.meta.url);
const _dirname = path.dirname(_filename);

/**
 * Create a BetterSQLite3Database instance for the seed CLI.
 *
 * @param dbPath - SQLite file path or ":memory:" for in‑memory DB.
 * @returns A Drizzle database instance wired to the v2 schema.
 */
export function createSeedDatabase(dbPath: string): import("drizzle-orm/better-sqlite3").BetterSQLite3Database<typeof schema> {
  const sqlite = new Database(dbPath);

  // Enable foreign keys (required by tests' PRAGMA foreign_key_check)
  sqlite.pragma("foreign_keys = true");

  const db = drizzle(sqlite, { schema });

  return db;
}

/**
 * Apply migrations to a seed database.
 *
 * The migrations folder lives in packages/api/drizzle/migrations; this function
 * resolves it relative to this file's location (scripts/seed/db.ts).
 *
 * @param db - A seed database instance from createSeedDatabase().
 * @param options.migrationsFolder - Override path to migrations (defaults to packages/api/drizzle/migrations).
 */
export async function applyMigrations(
  db: ReturnType<typeof createSeedDatabase>,
  options?: { migrationsFolder?: string }
): Promise<void> {
  // Resolve to packages/api/drizzle/migrations by default
  const migrationsFolder = options?.migrationsFolder ?? path.resolve(
    _dirname,
    "../../packages/api/drizzle/migrations"
  );

  await migrate(db, { migrationsFolder });
}

/**
 * Create a seed database and apply migrations in one call.
 *
 * @param dbPath - SQLite file path or ":memory:".
 * @param options.migrationsFolder - Override path to migrations.
 * @returns A ready‑to‑use database instance.
 */
export async function createAndMigrateSeedDatabase(
  dbPath: string,
  options?: { migrationsFolder?: string }
): Promise<ReturnType<typeof createSeedDatabase>> {
  const db = createSeedDatabase(dbPath);
  await applyMigrations(db, options);
  return db;
}
