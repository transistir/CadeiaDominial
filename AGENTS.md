# Repository Guidelines

## Project Layout

This repository is one part of a larger project directory. The convention is:

```
<project-root>/
├── CadeiaDominial/      # Main checkout, on integration branch `v2`
├── worktrees/           # Per-task worktrees (one branch per task)
└── workspaces/          # Kanban per-issue workspaces (orchestrator-managed)
```

- `docs/` holds primary deliverables: migration guides, architecture decisions, legacy references. Start here for context.
- `docs/legacy-django/` documents the historical Django implementation kept in `old/`.
- `old/` contains legacy Django artifacts; not the active codebase.
- `scripts/` holds the PostgreSQL → SQLite migration toolkit.
- `WORKFLOW.md` is a tool config consumed by an orchestrator — treat as data, not as documentation.

## Development Workflow

**One main checkout + one worktree per task.** The integration branch is **`v2`** (never `main` — `main` is the original GitHub default and is not the working branch). All new work happens on a worktree branched from `origin/v2`, opens a PR against `v2`, and is cleaned up after merge.

### Lifecycle

1. **Start from the main checkout on `v2`.** Run `git status` and `git branch --show-current` — expect `v2`. If you are already in a worktree, run `git worktree list` and `cd` to the worktree whose branch is `v2` (the main checkout).
2. Create a worktree for the task:
   ```bash
   git fetch origin
   mkdir -p ../worktrees
   git worktree add -b <type>/<short-task> ../worktrees/<short> origin/v2
   cd ../worktrees/<short>
   ```
3. Work in the worktree — all commits, pushes, and PR work happen here.
4. Push and open a PR against `v2`.
5. After CI passes and the PR is merged, return to the main checkout, clean up, and pull the new `v2` tip:
   ```bash
   cd ../../CadeiaDominial
   git status
   git branch --show-current  # should be v2
   git worktree remove --force ../worktrees/<short>
   git branch -D <type>/<short-task>
   git push origin --delete <type>/<short-task> 2>/dev/null  # OK if already gone
   git remote prune origin
   git pull origin v2
   ```

### Conventions

- **PR base**: `v2` (or `docs/roadmap-and-pending-decisions` for roadmap/spec updates — see below).
- **Branch name**: `<type>/<short-task>` (Conventional Commits type: `feat`, `fix`, `docs`, `refactor`, `chore`, …).
- **PR title**: Conventional Commits subject, e.g. `feat: add JWT-based user authentication`.

### Don't

- **Don't open PRs against `main`** — it exists as a GitHub default but is not the working branch.
- **Don't commit directly to `v2`** — always go through a worktree + PR. Trivial project-config edits (e.g. `WORKFLOW.md`) are the only exception, and only with explicit user approval.
- **Don't leave worktrees behind** after a merge. Cleanup is part of the lifecycle, not optional.
- **Don't put task branches in the main checkout** — use `git worktree add` so parallel work doesn't fight over the working tree.
- **Don't commit agent scratch files** (e.g. `docs/ERD_*.png` rendered by `mmdr`) — keep them untracked, or use `mmdr`'s `--out` to write elsewhere.

### Long-lived branch: `docs/roadmap-and-pending-decisions`

This branch tracks the roadmap and pending decisions. It is also kept as a long-lived worktree. Do **not** clean it up after a PR — it accumulates multiple task PRs and is periodically merged into `v2`. New roadmap-related task branches fork from `origin/docs/roadmap-and-pending-decisions` instead of `origin/v2`.

`docs/roadmap-and-pending-decisions/TASKS.md` and `SCHEMA_DECISOES_PENDENTES.md` are the authoritative source of pending decisions. Read them before starting any task that might already be tracked.

## Build, Test, and Development Commands

This repository snapshot is documentation-focused; the TypeScript monorepo described in `README.md` and `docs/MIGRATION_GUIDE.md` is not present here. When working against the full monorepo:

```bash
pnpm install                  # Install workspace dependencies (one-time)
pnpm dev                      # Start API + web together
pnpm -C packages/web dev      # Frontend dev server
pnpm -C packages/api dev      # API dev server
pnpm -C packages/api db:generate
pnpm -C packages/api db:migrate:local
pnpm test                     # Vitest + Playwright
pnpm format && pnpm lint
```

If you only touch `docs/`, no build step is required.

## Coding Style & Naming Conventions

- Documentation is Markdown; keep headings structured and sentences concise.
- Follow existing naming patterns for docs (e.g., `MIGRATION_GUIDE.md`, `ARCHITECTURE_DECISIONS.md`).
- The target TypeScript stack (per `docs/MIGRATION_GUIDE.md`) uses ESLint + Prettier, strict TypeScript, and minimal `any`.

## Testing Guidelines

- This documentation snapshot has no configured automated test runner. When working against the full monorepo, use Vitest and Playwright with an 80% coverage target.
- For frontend visual/interaction checks, use Agent Browser (`agent-browser` or `npx @vercel-labs/agent-browser`) and document results in the relevant PRD or progress notes.

## Commit & Pull Request Guidelines

- Commit messages follow Conventional Commits, optionally scoped, e.g. `feat(auth): add JWT validation`.
- Use short, imperative subjects and include context in the body when changes affect migration or architecture.
- PRs include a clear summary, link any relevant issue, and note which docs were updated.

## Migration & Architecture Notes

- Update `docs/ARCHITECTURE_DECISIONS.md` when making material architecture changes.
- Use `docs/legacy-django/` to cross-reference legacy behaviors during migration work.
- React Flow is the chosen tree visualization library; see `docs/MIGRATION_GUIDE.md` for usage notes.
