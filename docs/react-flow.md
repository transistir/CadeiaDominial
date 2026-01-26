# React Flow Quick Reference

## Purpose
Standardize how we represent the cadeia dominial graph in React Flow and the JSON format produced by the SQLite export script.

## Install (packages/web)

```bash
pnpm add @xyflow/react
```

## Data Shape

The script outputs a JSON object with:

- `nodes`: array of React Flow nodes
- `edges`: array of React Flow edges
- `viewport` (optional)

Minimal structure:

```json
{
  "nodes": [
    { "id": "doc-1", "position": { "x": 0, "y": 0 }, "data": { "label": "M123" } }
  ],
  "edges": [
    { "id": "lanc-10", "source": "doc-1", "target": "doc-2" }
  ],
  "viewport": { "x": 0, "y": 0, "zoom": 1 }
}
```

## Domain Mapping

- **Documento** → Node
  - `id`: `doc-<documento.id>`
  - `data`: include `numero`, `tipo`, `cartorio`, `data`, `livro`, `folha`
- **Lancamento** → Edge (when `documento_origem` exists)
  - `id`: `lanc-<lancamento.id>`
  - `source`: `doc-<documento_origem>`
  - `target`: `doc-<documento>`
  - **Note:** Lancamentos are not separate nodes; they only supply origin data for edges.
  - **Special case:** `inicio_matricula` always has one or more origins and is the primary source of edges.
- **Fim de cadeia** → Synthetic leaf node
  - `id`: `fim-<documento.id>-<indice>`
  - `data`: include `tipo_fim_cadeia`, `classificacao_fim_cadeia`
  - edge from `doc-<documento.id>` to `fim-...`

## Minimal Component

```tsx
import { ReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

export function CadeiaFlow({ nodes, edges }) {
  return <ReactFlow nodes={nodes} edges={edges} fitView />;
}
```

## Layout (Baseline)

- BFS layout:
  - `x = depth * 300`
  - `y = indexWithinDepth * 120`
- Keep layout logic in app code (not in the DB).
- Layout is visual only; it does not define semantic hierarchy.

## Graph Semantics

- The chain is a directed acyclic graph (DAG), not a strict tree.
- Nodes can have multiple origins; edges represent derivation.
- Depth is contextual; do not duplicate nodes to force a tree.
 - Root is the document that represents the current property (created at chain start and tied to `imovel.matricula`), not the largest registry number across cartórios.

## Conventions

- Node ids are stable and prefixed (`doc-`, `fim-`).
- Edge ids are stable and prefixed (`lanc-`).
- Use `data.label` for the node title (e.g., `M1234`).
