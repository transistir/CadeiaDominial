---
description: Execute ADD spec phase - create detailed specification with acceptance criteria
allowed-tools: Read, Write
context: fork
agent: spec
---

# ADD Spec Phase

Create a detailed specification with acceptance criteria.

## Your Task

### 1. Prerequisites Check

Find the most recent issue directory and verify:
- `01-research.md` is committed to git
- If not committed: Display error "Research phase not approved. Commit 01-research.md first."

### 2. Load Prior Artifacts

Read:
- `.project/issues/ISSUE-[id]/00-context.md` - Scope and boundaries
- `.project/issues/ISSUE-[id]/01-research.md` - Codebase patterns and constraints

### 3. Create Specification

Write to `.project/issues/ISSUE-[id]/02-spec.md`:

```markdown
# Specification

## Overview
[One paragraph: what this accomplishes and why]

## Acceptance Criteria
- [ ] [Specific, testable criterion 1]
- [ ] [Specific, testable criterion 2]
- [ ] [Continue for all criteria]

## Behavior

### [Scenario 1]
[Detailed description of expected behavior]

### [Scenario 2]
[Detailed description of expected behavior]

## Edge Cases

### [Edge Case 1]
- **Condition**: [When this happens]
- **Expected**: [What should happen]

## Out of Scope
- [Feature X] - will be addressed later
- [Enhancement Z] - future consideration
```

### 4. Guidelines

- Every acceptance criterion must be testable
- Be specific about behavior, not vague
- Stay within context.md scope boundaries
- Reference research findings where relevant

### 5. Display Completion

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Spec Phase Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Artifact: .project/issues/ISSUE-[id]/02-spec.md

Acceptance Criteria: [count] defined

Next Steps:
1. Review the specification
2. Commit 02-spec.md when satisfied (git commit = approval)
3. Run /tests
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
