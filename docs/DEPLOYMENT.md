# Deployment (Reproducible)

This doc captures the full, reproducible deployment flow for the Workers API and Pages web app.

## Prerequisites

- Node.js 20+
- pnpm 9+
- Cloudflare account with access to the target account and domain
- Cloudflare API token with these scopes:
  - Account > Cloudflare D1 > Edit
  - Account > Cloudflare Pages > Edit
  - Account > Workers Scripts > Edit
  - Account > Account Settings > Read
  - User > User Details > Read

## 1) Local setup

```bash
pnpm install
```

## 2) Cloudflare authentication

Set the API token for Wrangler:

```bash
export CLOUDFLARE_API_TOKEN="your-token-here"
```

Optional: set the account ID explicitly (otherwise Wrangler will infer it):

```bash
export CLOUDFLARE_ACCOUNT_ID="your-account-id"
```

## 3) Create D1 database

```bash
wrangler d1 create cadeia-dominial
```

Copy the returned `database_id` and update `packages/api/wrangler.toml`:

```toml
[[d1_databases]]
binding = "DB"
database_name = "cadeia-dominial"
migrations_dir = "drizzle/migrations"
database_id = "REPLACE_WITH_D1_ID"
```

## 4) Set API secrets

```bash
cd packages/api
wrangler secret put JWT_SECRET
```

## 5) Generate and apply migrations

```bash
pnpm db:generate
wrangler d1 migrations apply cadeia-dominial --config wrangler.toml
```

## 6) Deploy API (Workers)

```bash
cd ../../
pnpm --filter @cadeia/api run deploy
```

After deploy, note the API URL (e.g. `https://cadeia-dominial-api.<subdomain>.workers.dev`).

## 7) Configure and deploy Web (Pages)

Set the API base URL for the web build:

```bash
export VITE_API_BASE_URL="https://cadeia-dominial-api.<subdomain>.workers.dev"
```

Then deploy:

```bash
pnpm --filter @cadeia/web run build
pnpm --filter @cadeia/web run deploy
```

For local development, you can also set this in `packages/web/.env` using
`packages/web/.env.example` as a template.

## Environment Variables

### API (Workers)
- `JWT_SECRET`: Secret used to sign JWTs. Set with `wrangler secret put JWT_SECRET`.

### Web (Pages)
- `VITE_API_BASE_URL`: Base URL for the API (e.g. `https://<your-worker>.workers.dev`).

## D1 Bindings

- Binding name: `DB`
- Database name: `cadeia-dominial`
- `database_id` must match the DB created via `wrangler d1 create`.

## D1 Cheat Sheet

Local-first (recommended):

```bash
wrangler dev                          # Local Worker + local D1 by default
pnpm db:migrate:local                 # Apply Drizzle migrations locally
wrangler d1 execute cadeia-dominial --local --config packages/api/wrangler.toml --command="SELECT 1;"
wrangler d1 execute cadeia-dominial --local --config packages/api/wrangler.toml --file="./seeds/dev.sql"
```

If you run commands from `packages/api`, you can drop the `--config` flag.

Remote (use with care):

```bash
wrangler d1 execute cadeia-dominial --remote --config packages/api/wrangler.toml --command="SELECT 1;"
wrangler d1 migrations apply cadeia-dominial --config packages/api/wrangler.toml
wrangler dev --remote                 # Runs on Cloudflare infra
```

Remote bindings (local Worker, remote DB):

```toml
[[d1_databases]]
binding = "DB"
database_name = "cadeia-dominial"
database_id = "REPLACE_WITH_REMOTE_ID"
preview_database_id = "REPLACE_WITH_PREVIEW_ID"
remote = true
```

```bash
wrangler dev                          # Worker stays local, DB is remote
```
