# AGENTS.md — Cadeia Dominial

Conventions for any coding agent (Hermes, Claude Code, Codex) working in this repo.
Read this before touching code. Pairs with the repo's `CLAUDE.md` (legacy) and
the user's `~/.hermes/memory/memory.md` for cross-project facts.

## Output style

This project uses the **`i-have-adhd`** output style by default (every harness).
The skill is installed at:

- Hermes: `~/.hermes/skills/i-have-adhd/SKILL.md`
- Claude Code: `claude plugin install i-have-adhd@i-have-adhd`
- Codex: `codex plugin add i-have-adhd@i-have-adhd`

Lead with the next action, number multi-step work, restate state every turn, end
with one concrete next step. Full rules in the SKILL.md.

## Development queue — MANDATORY at session start

**`docs/produto-3/ROADMAP.md` is the single source of truth for what to work on.**

- At the START of every new session (any harness), read that file first and
  follow the R1–R9 queue in the order and with the gate exceptions defined
  there. Do not pick issues by recency or preference.
- `docs/PLANO_SPRINTS.md` is HISTORICAL — never plan from it.
- Reordering the queue requires explicit user approval, recorded in the
  roadmap file itself.
- Gates must be respected with their roadmap-defined scope: GATE-CLIENTE
  blocks R7, GATE-LUANDRO blocks only the production release/tag in R1, and
  GATE-PRODUTO blocks R9.
- Except for an explicit gate exception in the roadmap, mark each release
  block done before starting the next one.

## Stack

- **Monorepo:** pnpm workspaces
- **Frontend:** React + Vite + TanStack Query (in `packages/web`)
- **API:** Cloudflare Workers + D1 SQLite (in `packages/api`)
- **Shared types:** `packages/shared`
- **Seed scripts:** `scripts/seed` (TypeScript, raw better-sqlite3 for bulk inserts)
- **Schema:** Drizzle ORM (SQLite dialect); migrations live in `packages/api/drizzle/`
- **Test:** Vitest (jsdom for web, node for api/shared/seed)

## Build/test commands (always scoped)

```bash
# From the repo root
pnpm typecheck                       # all packages, 5 packages
pnpm test                            # all packages
pnpm --dir scripts/seed typecheck    # scoped — fast iteration
pnpm --dir scripts/seed test
pnpm --dir packages/web test
```

**PATH caveat:** pnpm lives at `/root/.hermes/node/bin` and is NOT on the default
PATH. If `pnpm` is not found, `export PATH=/root/.hermes/node/bin:$PATH` first.

## Schema decisions — CHECK BEFORE ADDING COLUMNS

The v2 schema removed many PII fields. Decisions are tracked in:
- `docs/db/SCHEMA_DECISOES_PENDENTES.md` (authoritative)
- Each schema file's docstring (`packages/api/drizzle/schema/*.ts`)

**Active decisions that commonly bite:**

| Tag | Decision | What it means |
|---|---|---|
| **Q5** | REMOVER cpf/rg/email/telefone from `pessoa` | Only `id, nome, created_at, updated_at, deleted_at`. Never insert into these removed columns. |
| **Q4** | No PII encryption for v2 pessoa | The `pessoa` entity is a *cartório attribution source* (public name in a property chain). No encryption needed. |
| **Q2=B** | Soft-delete via `deleted_at` | LGPD-compliant without breaking FKs. Use `deleted_at IS NULL` for "active" queries. |

**Always** read the schema file's docstring + `docs/db/SCHEMA_DECISOES_PENDENTES.md`
before adding a column. If a test fails with `table X has no column named Y`,
the answer is **almost never** to add the column — it's to remove the INSERT.

## PR cycle (luandro's standing rule)

**Loop `fix → Codex review → commit → Codex PR review` until all 3 frontier models
APPROVE.** Don't merge on partial consensus.

| Stage | Model | Use for |
|---|---|---|
| Implementation | **Sonnet 5** (`claude --model sonnet`) | Bug fixes, test adaptation, refactors, known recipes |
| Architecture / planning / final review | **Opus 5** (`claude --model opus`) | Design choices, risky refactors, cross-validation, sign-off |
| Runtime / sandbox review | **Codex GPT-5.6-sol xhigh** | PR readiness, final gate, code review |
| Fallback (reviews only) | **Z.AI GLM-5.2** | When Opus is unavailable — NOT for implementation |

**Codex sandbox limits:** Codex can't run scripts that import `better-sqlite3`
(ERR_MODULE_NOT_FOUND on tsx module resolution). Hand it file paths, not
script-execution requests. Opus/Sonnet with file access substitute well.

**Pre-merge gate:** Never merge without explicit human authorization. The 3-model
APPROVE is necessary, not sufficient — the user has the final say.

**Branch model (always):** development branches are cut FROM `develop` and PRs
target `develop` (tested on the test server). `main` only receives merge→tag
releases (PR `develop → main` + tag `vX.Y.Z` triggers prod deploy). Never open
a feature PR directly against `main`.

## Pre-commit hooks

ESLint, typecheck, and tests run automatically. **Fix root causes, don't bypass
with `--no-verify`.** Hook failures:

- ESLint: most are auto-fixable with `pnpm --dir <pkg> lint --fix`
- Typecheck: usually missing import or wrong type for a removed column (Q5)
- Tests: re-run with `pnpm --dir <pkg> test -- <pattern>` to scope

## Code style

- **TypeScript strict** — no `any` unless wrapped in a comment explaining why
- **Drizzle queries** for reads; **raw better-sqlite3** for bulk inserts (Drizzle
  is ~10× slower for 10k+ rows)
- **Tests colocated** with source as `*.test.ts` (Vitest auto-discovers)
- **Vitest `describe` blocks** named for the function under test

## Repo layout quick reference

```
.
├── packages/
│   ├── api/         # Cloudflare Workers + D1, Drizzle schema lives here
│   ├── web/         # React + Vite frontend
│   ├── shared/      # Cross-package types and utilities
│   ├── chain-topology/  # S-1 orchestrator (topology + PII filler)
│   └── legacy-fit/  # Legacy migration scripts
├── scripts/
│   └── seed/        # S-2 writer (raw SQL persistence)
├── docs/
│   └── db/          # Schema decisions, migration plans
└── worktrees/       # Active worktrees (one per PR)
```

## Don't

- Don't add cpf/rg/email/telefone columns to `pessoa` — see Q5 above
- Don't use Drizzle for bulk inserts in the seed — use raw better-sqlite3
- Don't use `claude --model claude-fable-5` — that name returns 400. Use `opus` or `sonnet`
- Don't merge without explicit user authorization, even if all 3 models APPROVE
- Don't read or commit `.env` files — credentials are redacted by default
