# Bootstrap Progress

Goal: bootstrap a minimal, deployable Cloudflare setup (Workers API + Pages web) that also runs locally with a clean monorepo structure, matching the architecture decisions in `docs/ARCHITECTURE_DECISIONS.md` and the migration guide in `docs/MIGRATION_GUIDE.md`.

## Architecture Anchors
- Frontend: React + Vite + TanStack Router
- Backend: Hono on Cloudflare Workers
- Database: Cloudflare D1 (SQLite) via Drizzle
- Visualization: React Flow
- Shared: Zod schemas + shared TypeScript types

## Latest Dependency Baseline
These are the target “starting point” versions for the bootstrap phase. Update only if a newer stable release is available at time of install.

- react: 19.2.3
- react-dom: 19.2.3
- vite: 7.3.1
- @tanstack/react-router: 1.157.15
- @tanstack/react-query: 5.90.19
- @xyflow/react: 12.10.0
- hono: 4.11.5
- @hono/zod-validator: 0.7.2
- drizzle-orm: 0.45.1
- drizzle-kit: 0.31.8
- zod: 4.1.5
- tailwindcss: 4.1.18
- typescript: 5.9.3
- wrangler: 4.56.0
- vitest: 4.0.17
- playwright: 1.57.0
- eslint: 9.39.2
- prettier: 3.8.0
- @cloudflare/workers-types: 4.20260122.0

## Multi-Stage Plan

### Stage 0 — Alignment & Inventory
- PRD-000: Confirm architecture decisions and scope boundaries

### Stage 1 — Monorepo Bootstrap
- PRD-001: Create pnpm workspace + turbo pipeline + package layout
- PRD-002: Shared types package wired into web + api

### Stage 2 — API Foundation (Cloudflare Workers)
- PRD-003: Hono app with health route, CORS, and typed bindings
- PRD-004: D1 + Drizzle schema + local migration flow
- PRD-005: Auth skeleton (JWT + D1 user table)

### Stage 3 — Web Foundation (Cloudflare Pages)
- PRD-006: Vite + React + TanStack Router baseline
- PRD-007: TanStack Query + API client wiring
- PRD-008: React Flow minimal screen with sample data

### Stage 4 — Tooling, CI, Deploy
- PRD-009: ESLint + Prettier + TypeScript strict config
- PRD-010: Vitest + Playwright baseline
- PRD-011: Cloudflare deploy config for Pages + Workers

### Stage 5 — Local Dev Experience
- PRD-012: Unified `pnpm dev` for web/api + local D1

## Progress Tracker

| PRD | File | Status | Notes |
| --- | ---- | ------ | ----- |
| PRD-000 | docs/prd/bootstrap/PRD-000-alignment.json | not-started | confirm scope and package versions |
| PRD-001 | docs/prd/bootstrap/PRD-001-monorepo.json | done | workspace + turbo + package layout |
| PRD-002 | docs/prd/bootstrap/PRD-002-shared.json | done | shared Zod schema + api/web consumption |
| PRD-003 | docs/prd/bootstrap/PRD-003-api-hono.json | done | Hono app with health + CORS |
| PRD-004 | docs/prd/bootstrap/PRD-004-d1-drizzle.json | done | D1 binding + Drizzle schema/migrations |
| PRD-005 | docs/prd/bootstrap/PRD-005-auth.json | done | JWT auth routes + users table |
| PRD-006 | docs/prd/bootstrap/PRD-006-web-vite.json | done | Vite + React + TanStack Router |
| PRD-007 | docs/prd/bootstrap/PRD-007-query-client.json | done | TanStack Query + health fetch |
| PRD-008 | docs/prd/bootstrap/PRD-008-react-flow.json | done | React Flow route with sample graph |
| PRD-009 | docs/prd/bootstrap/PRD-009-tooling.json | not-started | lint/format/types |
| PRD-010 | docs/prd/bootstrap/PRD-010-tests.json | not-started | vitest/playwright |
| PRD-011 | docs/prd/bootstrap/PRD-011-deploy.json | not-started | CF deploy |
| PRD-012 | docs/prd/bootstrap/PRD-012-local-dev.json | not-started | local dev setup |
