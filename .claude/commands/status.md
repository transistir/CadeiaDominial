---
description: Display current ADD workflow status based on artifacts
allowed-tools: Read, Bash
---

# ADD Workflow Status

Display the current state of the ADD workflow based on artifact files and git commits.

## Your Task

1. Find the most recent issue directory under `.project/issues/ISSUE-*/`
   - If none exists, display: "No ADD workflow found. Run /init <issue-id> to start."

2. For each artifact file, check:
   - Does the file exist?
   - Is it committed to git? Use: `git log -1 --format="%h" <file>`

3. Display status in this format:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ADD Workflow Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Issue: #[issue-id]
Directory: .project/issues/ISSUE-[id]/

Artifacts:
[✓] Context (committed: abc123)
[○] Research (not committed)
[ ] Spec (not created)
[ ] Tests (not created)
[ ] Plan (not created)
[ ] Review (not created)
[ ] QA (not created)

Legend:
  ✓ = committed (approved)
  ○ = exists but needs commit
  [ ] = not created

Next Action: [determine from table below]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Artifact Files to Check

- `00-context.md` → "Context"
- `01-research.md` → "Research"
- `02-spec.md` → "Spec"
- `03-tests.md` → "Tests"
- `04-plan.md` → "Plan"
- `05-review.md` → "Review"
- `06-qa.md` → "QA"

## Next Action Logic

| Last Committed | Next Action                   |
| -------------- | ----------------------------- |
| None           | Edit and commit 00-context.md |
| 00-context.md  | Run /research                 |
| 01-research.md | Run /spec                     |
| 02-spec.md     | Run /tests                    |
| 03-tests.md    | Run /plan (uses Codex)        |
| 04-plan.md     | Run /dev                      |
| Dev commits    | Run /review (uses Codex)      |
| 05-review.md   | Run /qa (Claude Code tests)   |
| 06-qa.md       | Workflow complete! Create PR  |
