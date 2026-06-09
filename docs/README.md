# CadeiaDominial — Documentation Index

This directory holds the project's primary documentation. Start here for navigation.

## 🗂 Structure

| Directory / file | Purpose |
|---|---|
| [`domain/`](./domain/) | Domain model — what a land-registry chain **is** (lançamentos, fim de cadeia, tree shape, D3 visualization) |
| [`db/`](./db/) | Database schema (v2 — the **current** target) |
| [`prd/`](./prd/) | Product Requirements Documents for the TypeScript monorepo bootstrap |
| [`legacy-django/`](./legacy-django/) | Reference docs for the historical Django/Postgres implementation (now frozen in `old/`) |
| [`ARCHITECTURE_DECISIONS.md`](./ARCHITECTURE_DECISIONS.md) | ADRs (Architecture Decision Records) for the v2 stack |
| [`MIGRATION_GUIDE.md`](./MIGRATION_GUIDE.md) | Full technical guide for the Django → TypeScript migration |
| [`MIGRATION_CHECKLIST.md`](./MIGRATION_CHECKLIST.md) | Phase-by-phase execution checklist (companion to MIGRATION_GUIDE) |
| [`DEPLOYMENT.md`](./DEPLOYMENT.md) | Cloudflare Workers + D1 deployment notes |
| [`DEVELOPMENT_FLOW.mermaid`](./DEVELOPMENT_FLOW.mermaid) | High-level development flow diagram |
| [`D1_IMPORT.md`](./D1_IMPORT.md) | Importing legacy data into Cloudflare D1 |
| [`D1_LOCAL_DEV.md`](./D1_LOCAL_DEV.md) | Running D1 locally for development |
| [`CODEX_COMMANDS.md`](./CODEX_COMMANDS.md) | Codex CLI command reference |

## 🚦 Where to start

- **New to the project?** → [`MIGRATION_GUIDE.md`](./MIGRATION_GUIDE.md) → [`ARCHITECTURE_DECISIONS.md`](./ARCHITECTURE_DECISIONS.md) → [`domain/overview.md`](./domain/overview.md)
- **Working on the schema?** → [`db/README.md`](./db/README.md) (read this first — it points to the **gate decisions** in `SCHEMA_DECISOES_PENDENTES.md`)
- **Implementing a feature in the v2 monorepo?** → [`prd/`](./prd/) for the relevant PRD
- **Cross-referencing legacy behavior?** → [`legacy-django/`](./legacy-django/)

## 🔗 Related

- `../TASKS.md` — Roadmap & task list (T-000 through T-403+)
- `../BOOTSTRAP_PROGRESS.md` — Monorepo bootstrap status
- `../README.md` — Top-level project README
