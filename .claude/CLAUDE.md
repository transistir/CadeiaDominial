# CadeiaDominial - Claude Code Configuration

Project-specific configuration for Claude Code with ADD workflow.

## ADD Workflow

Agent-Driven Development workflow with Claude Code + Codex integration.

**Key Features:**

- **Claude Code**: Handles research, spec, tests, dev, and QA phases
- **Codex**: Creates implementation plans and code reviews (10min timeout)
- **Git-based Approval**: Commit artifact = phase approved
- **Local Development**: Replaces GitHub Actions workflow

### Quick Start

```bash
# Initialize workflow for an issue
/init 123

# Execute phases (creates artifacts in .project/issues/ISSUE-123/)
/research    # Claude: Codebase analysis
/spec        # Claude: Write specification
/tests       # Claude: Design tests
/plan        # Codex: Implementation plan (10min)
/dev         # Claude: Implement code
/review      # Codex: Code review (10min)
/qa          # Claude: Run tests (Playwright + unit)

# Check status
/status
```

### Workflow

```
Issue → Context → Research → Spec → Tests → Plan → Dev → Review → QA → Complete
         ↓          ↓         ↓       ↓      ↓      ↓      ↓        ↓       ↓
      (commit)   (commit)  (commit) (commit) (Codex) (commits) (Codex)  (commit)
                                              ↓                  ↓
                                           (commit)          (commit)
```

**Approval Mechanism**: `git commit artifact.md` = phase approved

### Artifacts

| Phase    | Artifact       | Tool      | Description                            |
| -------- | -------------- | --------- | -------------------------------------- |
| context  | 00-context.md  | Human     | Scope and boundaries                   |
| research | 01-research.md | Claude    | Codebase analysis                      |
| spec     | 02-spec.md     | Claude    | Specification with acceptance criteria |
| tests    | 03-tests.md    | Claude    | Test specification                     |
| plan     | 04-plan.md     | **Codex** | Implementation plan (10min timeout)    |
| dev      | (commits)      | Claude    | Implementation commits                 |
| review   | 05-review.md   | **Codex** | Code review (10min timeout)            |
| qa       | 06-qa.md       | Claude    | QA report (tests + validation)         |

### Phase Details

**Human Phases:**

- **Context** (00-context.md): Human defines problem, scope, boundaries

**Claude Code Phases:**

- **Research** (/research): Analyzes codebase patterns, dependencies, constraints
- **Spec** (/spec): Creates specification with testable acceptance criteria
- **Tests** (/tests): Designs unit and E2E tests covering all criteria
- **Dev** (/dev): Implements the plan with atomic commits
- **QA** (/qa): Runs Playwright + unit tests, validates against spec

**Codex Phases (MCP Bridge):**

- **Plan** (/plan): Generates step-by-step implementation plan
- **Review** (/review): Reviews code against spec and plan

### Codex Integration

Codex is invoked via MCP bridge for complex planning and review:

```bash
# Plan phase uses consult_codex
- Query: Context + Spec + Tests → Plan
- Timeout: 600 seconds (10 minutes)
- Format: JSON

# Review phase uses consult_codex_with_stdin
- Stdin: git diff output
- Prompt: Spec + Plan → Review
- Timeout: 600 seconds (10 minutes)
- Format: JSON
```

### GitHub Actions

Only used for issue preprocessing:

- Human creates GitHub issue
- Codex analyzes and improves issue description
- Codex breaks issue into logical sub-issues
- Human approves breakdown

All implementation happens locally with Claude Code.

## Project Context

- **Migration**: Django → Next.js + Hono + Cloudflare D1
- **Architecture**: TypeScript monorepo with pnpm
- **Docs**: See `docs/` for migration guides
- **Testing**: Playwright (E2E) + Vitest (unit)

See `.claude/skills/add-workflow.md` for full workflow documentation.
