# Database — Schema v2 (current)

Documents the **current target** schema for the CadeiaDominial system (Drizzle ORM on Cloudflare D1 / SQLite).

## 🚦 STOP — read before doing schema work

> **Phase 0 (BLOCKING):** Six open decisions in [`SCHEMA_DECISOES_PENDENTES.md`](./SCHEMA_DECISOES_PENDENTES.md) must be answered by Luandro before any new schema code lands. See task **T-001** in `../../TASKS.md`.

## Files

| File | Purpose |
|---|---|
| [`SCHEMA_CONSOLIDATED.md`](./SCHEMA_CONSOLIDATED.md) | Consolidated v2 schema (canonical reference) |
| [`erd-v2.mmd`](./erd-v2.mmd) | Mermaid ERD of the v2 model |
| [`erd-v2-legend.md`](./erd-v2-legend.md) | Legend / column notes for the ERD |
| [`SCHEMA_CONSTRAINTS.md`](./SCHEMA_CONSTRAINTS.md) | Cross-table constraints (uniqueness, FK invariants) |
| [`SCHEMA_QUESTOES.md`](./SCHEMA_QUESTOES.md) | Open audit questions (Q1–Q25) about the v2 schema |
| [`SCHEMA_RESPOSTAS.md`](./SCHEMA_RESPOSTAS.md) | Answers to Q1–Q25 |
| [`legacy/`](./legacy/) | Per-table analyses of the **previous** Django schema (PascalCase tables) |

## Cross-reference

- The blindspot review of this schema is in `../../SCHEMA_V2_BLINDSPOT_REVIEW.md` (PR #15).
- The legacy Django model is documented in [`../legacy-django/03-database-models.md`](../legacy-django/03-database-models.md).
