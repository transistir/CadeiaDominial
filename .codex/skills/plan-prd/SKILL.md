---
name: plan-prd
description: Create a concrete implementation plan from one or more PRD JSON files (scope, milestones, dependencies, risks, tests).
metadata:
  short-description: Plan PRD implementation
---

# Plan PRD Implementation

## When to use
- The user asks for a plan, roadmap, milestones, or sequencing of PRD work.
- The user wants a multi-stage or phased implementation plan.

## Inputs to gather
- The PRD JSON file(s) (default: `docs/prd/bootstrap/*.json`).
- Constraints (time, team size, deploy targets, scope limits).
- Dependencies (libs, infra, data, external services).

## Workflow
1. Read the relevant PRD JSON files and `BOOTSTRAP_PROGRESS.md`.
2. Restate goals, scope, and non-goals.
3. Break work into stages with milestones and deliverables.
4. Note dependencies and ordering constraints.
5. Identify risks and mitigations.
6. Define a minimal test/verification plan.
7. Propose a short execution order with small, reviewable chunks.

## Output format
- Goals and scope
- Stages/milestones (with PRD IDs)
- Dependencies and risks
- Test/verification plan
- Next immediate step
