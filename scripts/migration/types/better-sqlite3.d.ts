/**
 * Minimal ambient typings for better-sqlite3.
 *
 * The upstream `@types/better-sqlite3` package is not available in this
 * repo's offline pnpm store, so we declare only the surface used by
 * `legacy-fit.ts`. If `@types/better-sqlite3` is added later, delete this
 * file.
 */
declare module "better-sqlite3" {
  interface RunResult {
    changes: number;
    lastInsertRowid: number | bigint;
  }

  interface Statement {
    run(...params: unknown[]): RunResult;
    get(...params: unknown[]): unknown;
    all(...params: unknown[]): unknown[];
    iterate(...params: unknown[]): IterableIterator<unknown>;
  }

  interface Database {
    prepare(sql: string): Statement;
    exec(sql: string): Database;
    pragma(source: string, options?: { simple?: boolean }): unknown;
    transaction<F extends (...args: never[]) => unknown>(fn: F): F;
    close(): Database;
  }

  interface DatabaseConstructor {
    new (filename: string, options?: Record<string, unknown>): Database;
    (filename: string, options?: Record<string, unknown>): Database;
  }

  const Database: DatabaseConstructor;
  export = Database;
}
