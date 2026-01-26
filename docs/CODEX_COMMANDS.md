# Codex Commands (Repo)

This repo uses Codex skills (shared, repo-scoped) instead of deprecated custom prompts. Skills are invoked explicitly with `$skill-name` in the Codex CLI or IDE, or triggered implicitly when the request matches their descriptions.

## Available skills

- `plan-prd`
  - Use for: turning PRD JSON files into a staged implementation plan.
  - Invoke: `$plan-prd` or ask for a PRD implementation plan.

- `review-implementation`
  - Use for: reviewing changes for correctness, risks, and missing tests.
  - Invoke: `$review-implementation` or ask for a code review.

- `implement-prd`
  - Use for: implementing specific PRD steps in the repo.
  - Invoke: `$implement-prd` and reference the PRD file(s) to implement.

## Typical usage patterns

- Plan a stage:
  - Example: `$plan-prd PRD=docs/prd/bootstrap/PRD-003-api-hono.json`
- Review changes:
  - Example: `$review-implementation` then mention the files or PRD.
- Implement a PRD:
  - Example: `$implement-prd PRD=docs/prd/bootstrap/PRD-006-web-vite.json`

## Notes

- Skills are stored under `.codex/skills/` and are shared through the repo.
- If you want user-scoped slash commands, Codex supports deprecated custom prompts under `~/.codex/prompts/` and invokes them as `/prompts:<name>`.
