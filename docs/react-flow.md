# React Flow Quick Reference

## Purpose
Standardize how we represent the cadeia dominial graph in React Flow and the JSON format produced by the SQLite export script.

## Install (packages/web)

```bash
pnpm add reactflow
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

## Minimal Component

```tsx
import { ReactFlow } from "reactflow";
import "reactflow/dist/style.css";

export function CadeiaFlow({ nodes, edges }) {
  return <ReactFlow nodes={nodes} edges={edges} fitView />;
}
```

## Layout (Baseline)

- BFS layout:
  - `x = depth * 300`
  - `y = indexWithinDepth * 120`
- Keep layout logic in app code (not in the DB).

## Conventions

- Node ids are stable and prefixed (`doc-`, `fim-`).
- Edge ids are stable and prefixed (`lanc-`).
- Use `data.label` for the node title (e.g., `M1234`).
