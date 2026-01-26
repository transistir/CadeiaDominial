# Deployment Notes

## Environment Variables

### API (Workers)
- `JWT_SECRET`: Secret used to sign JWTs. Set with `wrangler secret put JWT_SECRET`.

### Web (Pages)
- `VITE_API_BASE_URL`: Base URL for the API (e.g. `https://<your-worker>.workers.dev`).

## D1 Bindings

- Binding name: `DB`
- Database name: `cadeiadominial-db`
- Set `database_id` in `packages/api/wrangler.toml` after creating the D1 database.

## Deploy Commands

### API (Workers)
```bash
pnpm --filter @cadeia/api db:generate
pnpm --filter @cadeia/api deploy
```

### Web (Pages)
```bash
pnpm --filter @cadeia/web build
pnpm --filter @cadeia/web deploy
```
