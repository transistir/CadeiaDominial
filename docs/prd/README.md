# Product Requirements Documents

PRDs for the TypeScript monorepo bootstrap. Each PRD is a JSON file consumed by the Codex PRD workflow (see `.codex/`).

## Index

| PRD | Title | Status |
|---|---|---|
| PRD-000 | Alignment & preflight | bootstrap |
| PRD-001 | Monorepo scaffolding (pnpm workspaces + Turborepo) | bootstrap |
| PRD-002 | Shared package (types, utils) | bootstrap |
| PRD-003 | API service (Hono) | bootstrap |
| PRD-004 | D1 + Drizzle ORM integration | bootstrap |
| PRD-005 | Authentication (Auth.js / Clerk) | bootstrap |
| PRD-006 | Web app (Vite + React) | bootstrap |
| PRD-007 | TanStack Query client setup | bootstrap |
| PRD-008 | React Flow chain visualization | bootstrap |
| PRD-009 | Tooling (ESLint, Prettier, TypeScript strict) | bootstrap |
| PRD-010 | Testing (Vitest + Playwright, 80% coverage) | bootstrap |
| PRD-011 | Deployment (Cloudflare Workers + D1) | bootstrap |
| PRD-012 | Local dev environment | bootstrap |
| PRD-013 | ADR implementation | bootstrap |
| PRD-014 | PDF export of chain reports | bootstrap |
| PRD-015 | File storage (R2) | bootstrap |

## How to use

- Codex: `plan-prd <file>` → `implement-prd <file>` → `review-implementation <file>`
- See `../../.codex/` for skill definitions.
- See `../../BOOTSTRAP_PROGRESS.md` for execution status.

## Renaming policy

The PRD filename (`PRD-NNN-slug.json`) is the stable identifier referenced by `.codex/` skills and the bootstrap progress tracker. **Do not rename these files** without updating the references in `.codex/` and `BOOTSTRAP_PROGRESS.md`.
