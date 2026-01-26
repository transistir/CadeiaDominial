---
description: Execute ADD QA phase - run tests (Playwright + unit tests)
allowed-tools: Read, Bash, Write
---

# ADD QA Phase (Testing)

Run automated tests to verify the implementation.

## Your Task

### 1. Prerequisites Check

Find the most recent issue directory and verify:

- `05-review.md` is committed to git (Codex review approved)
- If not committed: Display error "Review phase not approved. Commit 05-review.md first."

### 2. Load Test Context

Read these files from `.project/issues/ISSUE-[id]/`:

- `02-spec.md` - Acceptance criteria to verify
- `03-tests.md` - Test specifications

### 3. Run Unit Tests

Execute the project's unit test suite:

- Use appropriate test runner (e.g., `pnpm test`, `npm test`, `pytest`)
- Capture full output including pass/fail counts
- Note any failing tests

### 4. Run E2E Tests (if Playwright available)

If Playwright is configured:

- Run E2E test suite
- Test critical user workflows
- Capture screenshots/videos of failures
- Note any flaky tests

### 5. Manual Verification (if needed)

For acceptance criteria not covered by automated tests:

- Manually verify functionality
- Document steps taken
- Record observations

### 6. Write QA Report

Create `.project/issues/ISSUE-[id]/06-qa.md` with:

```markdown
# QA Report

## Environment

- Commit SHA: [git rev-parse HEAD]
- Tested at: [timestamp]
- Branch: [git branch name]

## Unit Test Results
```

[Paste test runner output]

```

**Summary**: X passed, Y failed

## E2E Test Results (if applicable)

```

[Paste Playwright output]

```

**Summary**: X passed, Y failed

## Spec Verification

| Acceptance Criterion | Test Coverage | Result | Notes |
|---------------------|---------------|--------|-------|
| [Criterion 1]       | unit test     | ✅ PASS | |
| [Criterion 2]       | manual        | ✅ PASS | [How verified] |
| [Criterion 3]       | e2e test      | ❌ FAIL | [Issue description] |

## Issues Found

### Critical
1. [Issue] - [Description and impact]

### Major
1. [Issue] - [Description]

### Minor
1. [Issue] - [Description]

## Verdict

**PASS** / **FAIL**

- All acceptance criteria: ✅ / ❌
- No critical/major issues: ✅ / ❌

## Recommendations

- [Any suggestions for improvement]
- [Performance observations]
- [Test coverage gaps]
```

### 7. Display Completion

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QA Phase Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Artifact: .project/issues/ISSUE-[id]/06-qa.md

Verdict: [PASS/FAIL]
Unit Tests: [X]/[Y] passed
E2E Tests: [X]/[Y] passed
Issues: [count by severity]

Next Steps:
[If PASS]
1. Review QA report
2. Commit 06-qa.md
3. Create PR and link to issue

[If FAIL]
1. Review failing tests and issues
2. Fix implementation (/dev)
3. Re-run /review and /qa
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Notes

- Focus on running actual tests, not just code review
- Playwright tests may need browser setup first
- If tests don't exist yet, note this in the report
- QA should be objective: tests pass or fail
