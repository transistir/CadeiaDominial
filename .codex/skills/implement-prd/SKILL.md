---
name: implement-prd
description: Implement PRD JSON requirements into the repo with minimal, reviewable changes.
metadata:
  short-description: Implement PRD tasks
---

# Implement PRD

## When to use
- The user asks to implement one or more PRDs or specific PRD steps.

## Inputs to gather
- PRD JSON file(s) and any acceptance criteria.
- Target stage and status in `BOOTSTRAP_PROGRESS.md`.
- Required libraries or infra setup.

## Workflow
1. Read the PRD JSON and confirm scope.
2. Inspect current repo state for prerequisites.
3. Implement the smallest slice that satisfies the PRD steps.
4. Update progress tracking (PRD status/notes) when completed.
5. Provide test or verification steps.

## Output format
- What changed and why
- Files touched (paths)
- Verification steps
- Follow-up tasks or dependencies
