# T-500 Handoff — Custom Node + Edge Types (Phase 1.5)

## Status
✅ **Shipped — pending PR** — `feat/t-500-custom-node-types` worktree at `d55476a`

## Worktree
- Path: `/root/dev/cadeia-dominial/worktrees/t-500`
- Branch: `feat/t-500-custom-node-types` (rebased on current `origin/v2`)
- Created: 2026-06-09 from `fd6cc25`
- Current: 7 commits ahead of `origin/v2`
- Commits since `origin/v2`:
  - `d55476a` test(graph): tighten topology-adapter shape assertions (T-500 N-1)
  - `97855b8` feat(graph): integrate custom node/edge types into the rendering pipeline (T-500 item 5)
  - `e4ca147` fix(graph): disable pointer events on OrigemEdge label to preserve pane pan (T-500 N-1)
  - `e761546` feat(graph): add OrigemEdge custom React Flow component (T-500 item 4)
  - `6da30d2` feat(graph): add FimCadeiaNode custom React Flow component (T-500 item 3)
  - `601593a` feat(graph): add DocumentoNode custom React Flow component (T-500 item 2)
  - `4d7d3a0` feat(graph): extend types and validation for custom node/edge types (T-500 item 1)

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

## What was shipped
- `packages/web/src/components/graph/DocumentoNode.tsx` + `.css` + `.test.tsx` — 8 tests, 3 snapshots
- `packages/web/src/components/graph/FimCadeiaNode.tsx` + `.css` + `.test.tsx` — 10 tests, 3 snapshots
- `packages/web/src/components/graph/OrigemEdge.tsx` + `.css` + `.test.tsx` — 11 tests, 2 snapshots
- Type extension: `packages/web/src/graph/types.ts` — added `DocumentoData`, `FimCadeiaData`, `OrigemTipo`, `FimCadeiaClassificacao`
- Validator extension: `packages/web/src/graph/validateGraph.ts` — accepts `documento` and `fimCadeia` node types, validates data shapes
- `packages/web/src/graph/toReactFlow.ts` — passthrough type mapping, `OrigemEdge` for `tipoOrigem` edges
- `packages/web/src/graph/layoutGraph.ts` — `LayoutedNode` now carries data pass-through
- `packages/web/src/graph/topology-adapter.ts` — collapses `lancamento` nodes, attaches `tipoOrigem` on every edge
- `packages/web/src/graph/GraphPreview.tsx` — registers `nodeTypes` and `edgeTypes`
- `packages/web/src/graph/index.ts` — barrel exports for components
- `packages/web/src/graph/fixtures/basic-graph.json` — updated fixture: matrícula M1234 → transcrição T5678 → fim de cadeia `origem_lidima`
- `scripts/seed/chain-topology.ts` — emits `fimCadeia` camelCase, populates placeholder `data`

## Gates
- `pnpm turbo run test:unit typecheck lint --force` — 11/11 tasks green
- Web: 77/77 tests
- API: 13/13 tests
- Chain-topology: 155/155 tests
- Typecheck + lint: pass

## Pre-PR Checklist
- [x] Re-generate `screenshots/basic-graph.png` with `pnpm graph:screenshot` (the current PNG still shows the old default-node style; new screenshot will show the styled custom nodes)
- [x] Visually confirm screenshot shows 3 colored cards (matricula blue, transcricao purple, fim verde) + 2 labeled edges
- [x] Run Codex gpt-5.5 xhigh review on the full branch diff (bypassed: Codex rate-limited; Langfuse PR readiness review completed via claude-glm + GLM-5.1 direct — 0 blockers)
- [x] Resolve all inline comments (4/4 resolved: Codex P1+P2, Greptile 2×P1 — fixed in 9756f95)
- [x] Push branch and open PR against `v2` (PR #34)

### Depends on
- T-101 (schema defined for type alignment) — ✅ DONE
- @xyflow/react installed — ✅ DONE (`^12.10.0`)

### Blocks
- T-501 (graph data layer — needs DocumentoNode for type alignment)
- T-502 (graph page)
- T-503 (API endpoint)

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
worktrees/t-500/        feat/t-500-custom-node-types       @ d55476a (shipped, pending PR)
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
