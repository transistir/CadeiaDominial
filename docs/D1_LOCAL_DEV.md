# D1: Local vs Remote (Simple Guide)

This is the simplest way to work with D1 in this repo.

## TL;DR

Most days:

```bash
pnpm dev
pnpm db:migrate:local
```

Need a quick local query?

```bash
wrangler d1 execute cadeia-dominial --local --config packages/api/wrangler.toml --command="SELECT 1;"
```

## What to Know (One Minute)

- `wrangler dev` = local Worker + local D1 (safe, default).
- `wrangler dev --remote` = remote Worker + remote D1 (dangerous).
- `wrangler d1 execute --local` = local DB.
- `wrangler d1 execute --remote` = remote DB.
- Wrangler commands use the database name `cadeia-dominial` (not the binding `DB`).

## D1 Binding (Wrangler Config)

`packages/api/wrangler.toml` must define the D1 binding used by the Worker:

```toml
[[d1_databases]]
binding = "DB"
database_name = "cadeia-dominial"
migrations_dir = "drizzle/migrations"
database_id = "REPLACE_WITH_REMOTE_ID"
```

`wrangler d1 create` creates a remote D1 database and returns the `database_id`
you must place in the config.

## Local Development (Default)

### 1) Start the local Worker

```bash
pnpm dev
# or
cd packages/api && pnpm dev
```

Wrangler runs local mode by default. Your Worker uses a local-only D1 database
unless you pass `--remote`.

### 2) Apply schema and run queries locally

Use project scripts for Drizzle migrations:

```bash
pnpm db:generate
pnpm db:migrate:local
```

Or run SQL directly against the local database:

```bash
wrangler d1 execute cadeia-dominial --local --config packages/api/wrangler.toml --command="SELECT 1;"
wrangler d1 execute cadeia-dominial --local --config packages/api/wrangler.toml --file="./seeds/dev.sql"
```

If you run the commands from `packages/api`, you can drop the `--config` flag:

```bash
wrangler d1 execute cadeia-dominial --local --command="SELECT 1;"
```

Without `--local`, `wrangler d1 execute` targets the remote database.

### 3) Persist and inspect local data

Wrangler persists local data by default and stores local data under
`.wrangler/state`. To control the location, set a known path:

```bash
wrangler dev --persist-to=./.wrangler/local-state
```

When you use `--persist-to`, you can find the D1 SQLite file under that
directory and open it in any SQLite GUI or query it directly. Use the same
`--persist-to` value for any `wrangler d1 execute --local` commands you run.

If you need a clean slate, drop tables before recreating them.

## Remote Development (Use Carefully)

To run SQL against the remote database, use `--remote`:

```bash
wrangler d1 execute cadeia-dominial --remote --config packages/api/wrangler.toml --file="./drizzle/migrations/0001_init.sql"
```

## Decision Table (Which Mode to Use)

| You want to... | Do this | Why |
| --- | --- | --- |
| Build features safely | `wrangler dev` | Local Worker + local DB |
| Apply schema locally | `pnpm db:migrate:local` | No risk to prod |
| Run a quick local query | `wrangler d1 execute ... --local` | Local DB only |
| Test with real data but keep local speed | Remote bindings | Local Worker, remote DB |
| Test on Cloudflare infra | `wrangler dev --remote` | Runs in Cloudflare |
| Change production schema/data | `wrangler d1 ... --remote` | Only way to reach prod |

### Remote bindings (local Worker, remote DB)

If you need to keep your Worker running locally while connecting to a remote D1
database, Cloudflare supports remote bindings in local development. D1 is
supported for remote binding connections. To enable it, mark the binding as
remote:

```toml
[[d1_databases]]
binding = "DB"
database_name = "cadeia-dominial"
database_id = "REPLACE_WITH_REMOTE_ID"
preview_database_id = "REPLACE_WITH_PREVIEW_ID"
remote = true
```

This keeps your Worker local, but all D1 calls go to the remote database.
If `preview_database_id` is set, remote bindings target that preview database
instead of production.

If you are on an older Wrangler version that still requires experimental
remote bindings, use `experimental_remote = true` and run
`wrangler dev --x-remote-bindings`.

To preview your Worker on Cloudflare infrastructure (including remote D1),
start the dev server with:

```bash
wrangler dev --remote
```

Changes made in remote mode are irreversible, so use it carefully.

## Safety Checklist

- Default to local (`wrangler dev`, `--local`).
- Use `--remote` only when you intend to change production data.
- Prefer `preview_database_id` for remote bindings so you don't hit prod.
- Local data lives under `.wrangler/state` unless you set `--persist-to`.
