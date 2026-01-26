---
name: review-implementation
description: Review an implementation for correctness, risk, tests, and maintainability.
metadata:
  short-description: Review implementation
---

# Review Implementation

## When to use
- The user asks for a review, critique, or validation of changes.
- The user requests a check for regressions, risks, or missing tests.

## Inputs to gather
- The diff or files changed.
- The PRD(s) being implemented.
- Any acceptance criteria or expected behavior.

## Review checklist
- Correctness and edge cases
- Data validation and error handling
- Security and auth boundaries
- Performance and scalability risks
- Consistency with architecture decisions
- Tests added/updated and gaps
- Developer UX (build, lint, dev flow)

## Output format
- Findings ordered by severity with file references
- Open questions and assumptions
- Suggested tests or verification steps
- Short change summary (only after findings)
