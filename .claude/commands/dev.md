---
description: Execute ADD dev phase - implement the approved plan step by step
allowed-tools: Read, Write, Edit, Grep, Glob, Bash
context: fork
agent: dev
---

# ADD Dev Phase

Execute the development/implementation phase of the ADD workflow.

## Prerequisites Check

Find the most recent issue directory and verify:

- `04-plan.md` is committed to git
- If not committed: Display error "Plan phase not approved. Commit 04-plan.md first."

## Load Implementation Plan

Read the approved plan:
@.project/issues/ISSUE-{issue_id}/{sub_id}/04-plan.md

Also have available:

- Spec: @.project/issues/ISSUE-{issue_id}/{sub_id}/02-spec.md
- Tests: @.project/issues/ISSUE-{issue_id}/{sub_id}/03-tests.md

## Implementation Process

As the dev agent, you have full tool access. Execute the plan:

### 1. Follow the Plan Exactly

- Execute each step in order
- Make the specified changes to the specified files
- Verify each step before moving to next

### 2. Test-Driven Approach

- Run tests frequently during implementation
- Fix failures before continuing
- Don't commit broken code

### 3. Small Commits

- Commit after each logical step
- Use clear commit messages
- Reference spec criteria

### 4. Convention-Following

- Match existing code style
- Follow project patterns
- Respect linting/formatting rules

## Commit Message Format

```
type(scope): description

- Detail 1
- Detail 2

Implements: [spec criterion reference]
```

Types: feat, fix, refactor, test, docs, chore

## Workflow

1. Read the approved plan
2. For each step in the plan:
   - Make the specified changes
   - Verify the step (as described in plan)
   - Commit with clear message
3. Run full test suite
4. Report completion status

## Deviation Handling

If you must deviate from the plan:

1. Document the deviation
2. Explain why it was necessary
3. Note in decisions.md if significant

## Post-Dev

After completing implementation, display:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Dev Phase Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Implementation Summary:

## Commits Made
[List commits with hashes and messages]

## Plan Deviations
[None or description of changes from plan]

## Test Results
- [Test suite status]

## Files Changed
[List of files modified/created]

Next Steps:
1. Review the implementation
2. Run /review for Codex code review
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Error Handling

If implementation fails:

- Don't leave code in broken state
- Revert partial changes if necessary
- Document what went wrong
- Report the issue clearly

If tests fail:

- Try to fix within plan scope
- Don't add features not in plan
- Escalate if blocked
