# ADD Agents

Specialized agents for the Agent-Driven Development workflow.

## Agents

| Agent | Purpose | Tools |
|-------|---------|-------|
| `research` | Codebase analysis (read-only) | Read, Grep, Glob |
| `spec` | Specification writing | Read, Write |
| `tests` | Test design | Read, Write |
| `plan` | Implementation planning | Read, Write |
| `dev` | Full development access | All tools |
| `qa` | Quality assurance | Read, Bash |

## Usage

Agents are automatically invoked by their respective commands.

For example, `/research` invokes the `research` agent to analyze the codebase and create `01-research.md`.
