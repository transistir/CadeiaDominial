---
description: Initialize ADD workflow for an issue
argument-hint: <issue-id>
allowed-tools: Read, Write, Bash
---

# Initialize ADD Workflow

Initialize the Agent-Driven Development workflow for issue `$ARGUMENTS`.

## Your Task

1. Create the artifacts directory:
   - Path: `.project/issues/ISSUE-$ARGUMENTS/`
   - Use `mkdir -p` to create the directory structure

2. Copy all template files from `.claude/templates/artifacts/` to the new directory:
   - `00-context.md`
   - `02-spec.md`
   - Other template files

3. Display initialization confirmation:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ADD Workflow Initialized
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Issue: #$ARGUMENTS
Artifacts: .project/issues/ISSUE-$ARGUMENTS/

Next Steps:
1. Edit 00-context.md to define scope and boundaries
2. Commit 00-context.md when ready (git commit = approval)
3. Run /research to analyze codebase
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
