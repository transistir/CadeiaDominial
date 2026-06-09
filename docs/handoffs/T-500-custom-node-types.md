# T-500 Handoff — Custom Node + Edge Types (Phase 1.5)

## Status
📋 **Ready to start** — `feat/t-500-custom-node-types` worktree at `fd6cc25` (v2 head)

## Worktree
- Path: `/root/dev/cadeia-dominial/worktrees/t-500`
- Branch: `feat/t-500-custom-node-types` (rebased on current `origin/v2`)
- Created: 2026-06-09 from `fd6cc25`
- Fresh: zero unpushed commits

## What landed in Phase 1.5 so far (PR #28 + #29)
The pipeline is in place but uses the default node type:
- `packages/web/src/graph/GraphPreview.tsx` — wraps `<ReactFlow>` with the pipeline
- `packages/web/src/graph/validateGraph.ts` — accepts `unknown`, returns typed `GraphJson`
- `packages/web/src/graph/layoutGraph.ts` — dagre LR layout (deterministic)
- `packages/web/src/graph/toReactFlow.ts` — adapter to ReactFlow node/edge shape
- `packages/web/src/graph/fixtures/basic-graph.json` — 3-node canonical fixture
- `packages/web/src/graph/{validateGraph,layoutGraph,toReactFlow,topology-adapter}.test.ts` — 24 unit tests
- `packages/web/src/graph/README.md` — pipeline docs
- `packages/web/src/routes/graph.tsx` — `/graph` route using `GraphPreview` + canonical fixture
- `packages/web/e2e/{graph,graph-screenshot}.spec.ts` — Playwright smoke + screenshot
- `screenshots/basic-graph.png` — 1280×720 regression baseline (288 KB)
- `screenshots/README.md` — regeneration docs
- Root `package.json` — `graph:screenshot` script

## What T-500 needs to ship
Per `docs/TASKS.md` T-500 description:
- `DocumentoNode` — matrícula, transcrição, averbação (card with numero, tipo, cartório, data)
- `FimCadeiaNode` — synthetic leaf (color-coded: origem lídima green, sem origem red, inconclusa yellow)
- `OrigemEdge` — edge type with origin label (matrícula/transcrição/fim_cadeia)
- Styling: type-based color scheme matching legacy D3 (matrícula=blue, transcrição=purple, registro=teal)

### Acceptance criteria
- Storybook or standalone page renders all 3 node types with sample data
- Nodes are responsive (readable at 50%-200% zoom)
- TypeScript: all props fully typed, no `any`
- Vitest: snapshot tests for each node type

### Depends on
- T-101 (schema defined for type alignment) — ✅ DONE
- @xyflow/react installed — ✅ DONE (`^12.10.0`)

### Blocks
- T-501 (graph data layer — needs DocumentoNode for type alignment)
- T-502 (graph page)
- T-503 (API endpoint)

## Where to put the new code
Per `docs/TASKS.md`: `packages/web/src/components/graph/`
- Currently doesn't exist. Create it.
- Use `nodeTypes` prop on `<ReactFlow>` to register custom node types
- Use `edgeTypes` prop for custom edge types

## Domain docs to read first
- `docs/domain/react-flow-quick-reference.md` — canonical mapping
- `docs/domain/tree-model.md` — DAG semantics
- `docs/domain/fim-de-cadeia.md` — end-of-chain classification
- `docs/domain/lancamento-tipos.md` — lancamento types (matrícula, transcrição, registro, averbação)

## T-200 schema types available (already merged in #32)
File: `scripts/seed/chain-topology.ts` (now in v2)
- `TopologyDocumento` — `{ id, tipo, cartorioId, data, numero, cadeiaId, parentDocumentoId }`
- `TopologyFimCadeia` — `{ id, classificacao, origemId }` (classificacao: 'origem_lidima' | 'sem_origem' | 'inconclusa')
- `TopologyLancamento` — `{ id, tipo, data, cartorioId, imovelId }` (tipo: 'registro' | 'averbacao' | 'inicio_matricula')
- `TopologyOrigem` — `{ id, tipo, lancamentoId, origemId }` (tipo: 'matricula' | 'transcricao' | 'fim_cadeia')
- `TopologyImovel` — `{ id, ... }`
- `TopologyImovelDocumento` — junction N:N

These are also re-exported from `packages/web/src/graph/topology-adapter.ts` as `TopologyImovel` and `TopologyImovelDocumento` (added in PR #33 post-merge fix).

## Strategy recommendation
1. **Start with `DocumentoNode`** (the most common type — uses inline data, no need for classification logic)
2. **Then `FimCadeiaNode`** (smaller, but introduces color-coding pattern)
3. **Last `OrigemEdge`** (needs label rendering, but reuses the existing edge color palette)
4. **Add to `GraphPreview.tsx` via `nodeTypes` / `edgeTypes` props** so the existing demo uses them
5. **Update the canonical `basic-graph.json` fixture** if needed to demonstrate all 3 types
6. **Re-screenshot baseline** — `pnpm graph:screenshot` regenerates `screenshots/basic-graph.png`
7. **Run gates**: `pnpm turbo run test:unit typecheck lint --force` (must be 11/11 green)
8. **PR-review loop** (skill: `pr-readiness-loop`):
   - Codex gpt-5.5 xhigh
   - Resolve all inline comments
   - Langfuse PR-readiness prompt → blockers=0 + pre-merge=0
   - User authorizes merge

## Files to reference
```
packages/web/src/graph/GraphPreview.tsx          # Where nodeTypes/edgeTypes get registered
packages/web/src/graph/fixtures/basic-graph.json # 3-node canonical: lanc-1 → doc-1, fim-1
packages/web/src/graph/index.ts                  # Barrel export — add new components here
packages/web/src/graph/README.md                 # Pipeline docs — update with new types
packages/web/src/routes/graph.tsx                # Consumer of GraphPreview
packages/web/e2e/graph-screenshot.spec.ts       # Smoke test for the demo
```

## Active worktrees (do NOT touch)
```
CadeiaDominial/         v2                            @ fd6cc25 ✓
worktrees/decisions/    docs/roadmap-and-pending-decisions  @ 1f69d94 (long-lived)
worktrees/t-001-v2/     feat/t-001-schema-decisions-v2     @ 7b33ccb (3 unpushed, owned by Hiure)
worktrees/t-500/        feat/t-500-custom-node-types       @ fd6cc25 (fresh, ready)
```

## Constraints reminder
- Path: `export PATH="/root/.hermes/node/bin:$PATH"` before any pnpm command
- Push: use `execute_code` Python + base64 extraheader (scanner masks `GH_TOKEN`/`GITHUB_TOKEN` in terminal)
- Models: glm 5.1, deepseek 4 pro, kimi 2.6, minimax m3 (provider: opencode-zen or opencode-go)
- Code review: Codex gpt-5.5 xhigh. Codex CLI hits usage limit — fall back to Langfuse PR-readiness
- `gh` user: `hiurequeiroz`. `env -u GITHUB_TOKEN -u GH_TOKEN` before `gh` calls
- Bot saturation: Greptile hits trial limit at ~50 reviews; Codex connector dedupes
- NEVER merge without user authorization + 0 unresolved comments
- Use `git commit -F /tmp/commit-msg.txt` for long messages

## Next session kickoff prompt suggestion
"Resume T-500 from handoff at `/root/dev/cadeia-dominial/worktrees/t-500`. Read the handoff, then start with DocumentoNode. Apply the pr-readiness-loop skill end-to-end. Report back when the PR is at 5/5 APROVA or when blocked."
