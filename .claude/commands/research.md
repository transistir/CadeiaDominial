---
description: Execute ADD research phase - analyze codebase patterns, dependencies, and constraints
argument-hint: [additional-context]
allowed-tools: Read, Grep, Glob, WebFetch, WebSearch, Write, Bash(cat:*), Bash(test:*), Bash(grep:*)
context: fork
agent: research
---

# ADD Research Phase

Execute the research phase of the ADD workflow.

## Your Task

### 1. Prerequisites Check

Find the most recent issue directory and verify:

- `00-context.md` is committed to git
- If not committed: Display error "Context not approved. Commit 00-context.md first."

### 2. Load Context

Read `.project/issues/ISSUE-[id]/00-context.md` to understand:

- Problem statement
- Scope and boundaries
- Success criteria

## Research Process

As the research agent, perform:

### 1. Local Codebase Analysis (always required)

- Find relevant existing code using Grep and Glob
- Identify patterns and conventions
- Understand dependencies and constraints
- Map the scope boundaries from context

### 2. External Research (when needed)

- Consult library documentation
- Research best practices
- Check security considerations

### 3. Risk Identification

- Technical risks and mitigations
- Dependencies on other work
- Open questions for spec phase

## Output

Write findings to the research artifact. The artifact path is:
`.project/issues/ISSUE-{issue_id}/{sub_id}/01-research.md`

Use this format:

```markdown
# Research

## Local Codebase Analysis

### Relevant Files Examined

- `path/to/file.ts` - [what was learned]
- `path/to/similar.ts` - [pattern identified]

### Patterns Identified

- [Pattern 1]: [description and where it's used]
- [Pattern 2]: [description and where it's used]

### Constraints Discovered

- [Constraint 1]: [why it matters]

## External Research (if applicable)

### Sources Consulted

- [Source 1]: [key findings]
- [Source 2]: [key findings]

### Key Findings

- [Finding 1]
- [Finding 2]

## Risks and Considerations

### Technical Risks

- [Risk 1]: [mitigation approach]

### Dependencies

- [Dependency on X]: [implications]

### Open Questions for Spec Phase

- [Question 1]
- [Question 2]
```

## Post-Research

After writing the artifact, display:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Research Phase Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Artifact: .project/issues/ISSUE-{id}/{sub}/01-research.md

Next Steps:
1. Review the research findings
2. Commit 01-research.md when satisfied (git commit = approval)
3. Run /spec
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
