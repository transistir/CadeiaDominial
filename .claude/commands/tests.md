---
description: Execute ADD tests phase - design tests that verify all acceptance criteria
allowed-tools: Read, Write
context: fork
agent: tests
---

# ADD Tests Phase

Design tests that verify all acceptance criteria.

## Your Task

### 1. Prerequisites Check

Find the most recent issue directory and verify:
- `02-spec.md` is committed to git
- If not committed: Display error "Spec phase not approved. Commit 02-spec.md first."

### 2. Load Prior Artifacts

Read:
- `.project/issues/ISSUE-[id]/02-spec.md` - Acceptance criteria to test
- `.project/issues/ISSUE-[id]/00-context.md` - Scope reference

### 3. Design Tests

Write to `.project/issues/ISSUE-[id]/03-tests.md`:

```markdown
# Test Specification

## Alignment Check
- [ ] Tests cover all acceptance criteria from spec
- [ ] Tests cover documented edge cases

## Unit Tests

| Test Name | Validates | Spec Criterion |
|-----------|-----------|----------------|
| `should_do_X_when_Y` | [Behavior] | Criterion 1 |
| `should_handle_Z` | [Edge case] | Edge Case 1 |

### Test Details

#### `should_do_X_when_Y`
```
Given: [preconditions]
When: [action]
Then: [expected result]
```

## E2E Tests

| Test Name | Validates | User Flow |
|-----------|-----------|-----------|
| `user_can_complete_flow` | [Full scenario] | [Description] |

### Test Details

#### `user_can_complete_flow`
```
1. [Step 1]
2. [Step 2]
3. [Verification]
```

## Not Tested (with justification)
- [Scenario X] - covered by existing tests in [file]
- [Scenario Y] - manual QA more appropriate
```

### 4. Guidelines

- Map every acceptance criterion to at least one test
- Use clear Given/When/Then format
- Keep unit tests fast and focused
- Use E2E sparingly for critical user flows
- Justify anything not tested

### 5. Display Completion

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tests Phase Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Artifact: .project/issues/ISSUE-[id]/03-tests.md

Tests Designed:
- Unit: [count]
- E2E: [count]

Next Steps:
1. Review the test specification
2. Commit 03-tests.md when satisfied (git commit = approval)
3. Run /plan (uses Codex)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
