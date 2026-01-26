# Repository Guidelines

## Project Structure & Module Organization

- `docs/` holds the primary deliverables: migration guides, architecture decisions, and legacy Django references. Start here for context.
- `docs/legacy-django/` documents the historical Django implementation that was moved to `old/`.
- `old/` contains legacy Django artifacts (and data files) kept for reference; it is not the active codebase.
- `scripts/` holds the PostgreSQL → SQLite migration toolkit (see `scripts/pg_sqlite_migration/`).
- `README.md` describes the target TypeScript monorepo and Cloudflare deployment plan.

## Build, Test, and Development Commands

This repository snapshot is documentation-focused; the TypeScript monorepo described in `README.md`/`docs/MIGRATION_GUIDE.md` is not present here. When working against the full monorepo, the intended commands are:

```bash
pnpm dev                       # Start API + web together
cd packages/web && pnpm dev    # Frontend dev server
cd packages/api && pnpm dev    # API dev server
cd packages/api && pnpm db:generate
cd packages/api && pnpm db:migrate:local
```

If you only touch docs, no build step is required.

## Coding Style & Naming Conventions

- Documentation is Markdown; keep headings structured and sentences concise.
- Follow existing naming patterns for docs (e.g., `MIGRATION_GUIDE.md`, `ARCHITECTURE_DECISIONS.md`).
- The target TypeScript stack (per `docs/MIGRATION_GUIDE.md`) expects ESLint + Prettier, strict TypeScript, and minimal `any` usage.

## Testing Guidelines

- The planned stack uses Vitest and Playwright with an 80% coverage target (see `docs/MIGRATION_GUIDE.md`).
- No automated test runner is configured in this repository snapshot; treat `old/` as reference-only unless instructed otherwise.
- For frontend verification (visual or interaction checks), use Agent Browser via `npx @vercel-labs/agent-browser` and document results in the relevant PRD or progress notes.

## Commit & Pull Request Guidelines

- Commit history follows Conventional Commits with optional scopes (e.g., `feat:`, `fix:`, `docs:`, `refactor:`).
- Use short, imperative subjects and include context in the body when changes affect migration or architecture.
- For PRs, include a clear summary, link any relevant issue, and note which docs were updated.

## Migration & Architecture Notes

- Update `docs/ARCHITECTURE_DECISIONS.md` when making material architecture changes.
- Use `docs/legacy-django/` to cross-reference legacy behaviors during migration work.
- React Flow is the chosen tree visualization library; reference `docs/MIGRATION_GUIDE.md` for usage notes and `docs/ARCHITECTURE_DECISIONS.md` for the decision record.

## AI Agent Workflows

This repository uses multiple AI agent systems for different development workflows:

### Claude Code (.claude/) - ADD Workflow

Issue-based Agent-Driven Development workflow for implementing features and fixes.

**Usage**: See `.claude/CLAUDE.md` for full documentation

```bash
/init 123        # Initialize issue workspace
/research        # Analyze codebase
/spec           # Write specification
/tests          # Design tests
/plan           # Codex: Generate implementation plan (10min)
/dev            # Implement code
/review         # Codex: Code review (10min)
/qa             # Run tests (Playwright + unit)
```

**Approval**: `git commit artifact.md` = phase approved

### Codex (.codex/) - PRD Workflow

Document-based development using PRD JSON files for bootstrapping the monorepo.

**Skills**:

- `plan-prd` - Create implementation roadmap from PRD JSON
- `implement-prd` - Execute PRD requirements
- `review-implementation` - Review changes for correctness and risks

**Files**: `docs/prd/bootstrap/*.json`, `BOOTSTRAP_PROGRESS.md`

### When to Use Which

- **ADD (.claude)**: GitHub issues, bug fixes, feature requests
- **PRD (.codex)**: Strategic bootstrap tasks, PRD-driven development

Both workflows can run in parallel without conflict.
