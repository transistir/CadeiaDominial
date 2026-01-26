---
skill: "add-workflow"
description: "Agent-Driven Development workflow with git-based approval"
category: "development"
---

# ADD Workflow

Agent-Driven Development workflow: structured phases with git-based approval.

## Quick Start

```bash
# Initialize workflow for an issue
/init 123

# Execute phases (creates artifacts in .project/issues/)
/research    # Creates 01-research.md
/spec        # Creates 02-spec.md
/tests       # Creates 03-tests.md
/plan        # Creates 04-plan.md
/dev         # Creates PR
/qa          # Creates 06-qa.md

# Check status
/status
```

## Workflow

```
Issue → Context → Research → Spec → Tests → Plan → Dev → QA → Complete
         ↓          ↓         ↓       ↓       ↓     ↓    ↓       ↓
      (commit)   (commit)  (commit) (commit) (commit) (auto) (commit)
```

## Approval Process

1. Each phase creates an artifact in `.project/issues/ISSUE-{id}/`
2. Review the artifact (human review)
3. **Commit to git** = approval
4. Move to next phase

## Artifacts

```
.project/issues/ISSUE-123/
├── 00-context.md     # Scope and boundaries
├── 01-research.md    # Codebase analysis
├── 02-spec.md        # Specification with acceptance criteria
├── 03-tests.md       # Test specification
├── 04-plan.md        # Implementation plan
├── 06-qa.md          # QA report + approval
└── decisions.md      # Decision log (optional)
```

## Commands Reference

| Command         | Purpose                |
| --------------- | ---------------------- |
| `/init <issue>` | Initialize workflow    |
| `/status`       | Show current status    |
| `/research`     | Execute research phase |
| `/spec`         | Write specification    |
| `/tests`        | Design tests           |
| `/plan`         | Create plan            |
| `/dev`          | Implement code         |
| `/qa`           | Run QA                 |
