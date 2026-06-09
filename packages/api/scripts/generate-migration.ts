#!/usr/bin/env -S npx tsx
/**
 * Bypass drizzle-kit's interactive TTY prompt by running the migration
 * generation programmatically. The CLI requires TTY for schema conflict
 * resolution; this script uses the same API without prompts.
 *
 * Usage: npx tsx scripts/generate-migration.ts [migration-name]
 *   default name: v2_full_schema
 */
import { readdirSync, writeFileSync, mkdirSync } from "node:fs";
import { resolve, join } from "node:path";
import {
  generateSQLiteDrizzleJson,
  generateSQLiteMigration,
} from "drizzle-kit/api";

const API_ROOT = resolve(__dirname, "..");
process.chdir(API_ROOT);

const SCHEMA_DIR = resolve(API_ROOT, "drizzle/schema");
// R5-2 (Codex round 5 MUST-FIX): also load the legacy scaffold
// (`drizzle/schema.ts` at the package root, one level up from
// `drizzle/schema/`). It defines `users` + `health_checks` which are
// required by `/auth/login` bootstrap and would be missing from
// fresh migrations otherwise.
const LEGACY_SCHEMA = resolve(API_ROOT, "drizzle/schema.ts");

async function main() {
  const schemaModules = readdirSync(SCHEMA_DIR).filter(
    (f) => f.endsWith(".ts") && f !== "index.ts"
  );
  const schema: Record<string, unknown> = {};
  for (const f of schemaModules) {
    const mod = await import(join(SCHEMA_DIR, f));
    Object.assign(schema, mod);
  }
  const idx = await import(join(SCHEMA_DIR, "index.ts"));
  Object.assign(schema, idx);

  // Load legacy scaffold (users + health_checks).
  const legacy = await import(LEGACY_SCHEMA);
  Object.assign(schema, legacy);

  const casing = "snake_case";

  try {
    // Generate the current schema snapshot.
    const current = await generateSQLiteDrizzleJson(schema, undefined, casing);

    // For a fresh start, prev is an empty snapshot.
    // The schema requires version, dialect, tables/enums/views/_meta,
    // PLUS id + prevId (from schemaHash).
    const prev = {
      version: "6",
      dialect: "sqlite",
      id: "",
      prevId: "",
      tables: {},
      enums: {},
      views: {},
      _meta: { tables: {}, columns: {} },
    } as never;

    // Diff prev → current to get the SQL statements.
    const sqlStatements = await generateSQLiteMigration(
      prev as never,
      current
    );

    if (sqlStatements.length === 0) {
      console.log("No schema changes; no migration needed.");
      process.exit(0);
    }

    const name = process.argv[2] || "v2_full_schema";
    const tag = `0000_${name}`;
    const sqlFile = `${tag}.sql`;
    const snapshotFile = `${tag}_snapshot.json`;

    const dir = resolve(API_ROOT, "drizzle/migrations");
    mkdirSync(join(dir, "meta"), { recursive: true });

    writeFileSync(join(dir, sqlFile), sqlStatements.join("\n") + "\n");
    // Snapshot must live under `meta/` so `drizzle-kit generate` (CLI) finds
    // it on subsequent runs — the standard layout is `meta/{tag}_snapshot.json`.
    writeFileSync(join(dir, "meta", snapshotFile), JSON.stringify(current, null, 2));

    const journal = {
      version: "7",
      dialect: "sqlite",
      entries: [
        {
          idx: 0,
          version: "6",
          when: Date.now(),
          tag,
          breakpoints: true,
        },
      ],
    };
    writeFileSync(join(dir, "meta/_journal.json"), JSON.stringify(journal, null, 2));

    const totalSql = sqlStatements.join("\n").length;
    console.log(`Migration '${tag}' generated:`);
    console.log(`  ${sqlFile}: ${totalSql} chars, ${sqlStatements.length} statements`);
    console.log(`  meta/_journal.json + ${snapshotFile}`);
  } catch (err) {
    console.error("ERR:", (err as Error).message);
    if ((err as Error).stack) console.error((err as Error).stack);
    process.exit(1);
  }
}

main();
