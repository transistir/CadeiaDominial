import { defineConfig } from "drizzle-kit";
import fs from "fs";
import path from "path";

function getLocalD1DB() {
  try {
    const basePath = path.resolve(
      ".wrangler/state/v3/d1/miniflare-D1DatabaseObject"
    );
    const dbFile = fs
      .readdirSync(basePath)
      .find((f) => f.endsWith(".sqlite"));

    if (!dbFile) {
      throw new Error(`No local D1 database found in ${basePath}`);
    }
    return path.join(basePath, dbFile);
  } catch (err) {
    console.warn(
      `Could not locate local D1 database: ${err instanceof Error ? err.message : String(err)}`
    );
    return null;
  }
}

export default defineConfig({
  dialect: "sqlite",
  // R5-2 (Codex round 5 MUST-FIX): load BOTH the v2 schema (index.ts)
  // AND the legacy scaffold tables (schema.ts) so migrations include
  // `users` + `health_checks` — required by `/auth/login` bootstrap.
  schema: ["./drizzle/schema.ts", "./drizzle/schema/index.ts"],
  out: "./drizzle/migrations",
  dbCredentials: {
    url: getLocalD1DB() ?? "file:./local.sqlite",
  },
});
