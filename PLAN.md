# PLAN: SQLite -> React Flow JSON (TypeScript Script)

## Goal
Create the simplest possible TypeScript script that reads `./sqlite3.sql` (which is a SQLite database file) and outputs a React Flow–compatible JSON (nodes + edges) for the cadeia dominial tree.

## Quick Answer: “Do we need a sqlite db running?”
No. SQLite is file-based; we can open the database file directly from a Node.js script. The `sqlite3.sql` file starts with the `SQLite format 3` header, which indicates it is already a SQLite database file, not a SQL dump.

## Research Summary (from legacy docs + web)

### Legacy Django / D3 tree expectations (docs)
- The legacy D3 tree consumes a hierarchical JSON where each node contains fields like `numero`, `tipo`, `lancamentos`, `tem_multiplas_origens`, and `origens`. The D3 code uses `d3.hierarchy(this.data)` and draws one node per document, with color based on `tipo`. (See `docs/legacy-django/06-frontend.md`)
- The chain link between documents is modeled via `Lancamento.documento_origem` (FK to Documento). End-of-chain info lives in `OrigemFimCadeia` with `indice_origem` (for multi-origin). (See `docs/legacy-django/03-database-models.md`)

### React Flow data model (web)
- React Flow expects a JSON object with `nodes` and `edges` arrays (and optional `viewport`).
- Each node requires `id`, `position`, and optional `data` and `type`.
- Each edge requires `id`, `source`, and `target` (plus optional fields like `type`, `label`).

### SQLite library options for Node/TypeScript (web)
- `better-sqlite3` provides a fast, synchronous API and is widely used.
- `sqlite3` is a long-standing async library with prebuilt binaries via `node-pre-gyp`.
- The `sqlite` package is a TypeScript-friendly wrapper over `sqlite3`.
- If native builds are problematic, `@sqlite.org/sqlite-wasm` is an alternative, but is more setup-heavy for Node scripts.

## Proposed Approach (MVP)

### Script Output
- Write `./reactflow.json` (or `./artifacts/reactflow.json`) in `ReactFlowJsonObject` shape:
  - `nodes: Node[]`
  - `edges: Edge[]`
  - `viewport` optional

### Input / CLI
- Minimal CLI arguments:
  - `--db ./sqlite3.sql` (default)
  - `--documento-id <id>` or `--imovel-id <id>` (scope the chain)
  - `--out ./reactflow.json` (default)

### Simple React + Vite Viewer (MVP)
- Create a minimal React + Vite app that loads the JSON and renders it in React Flow.
- Keep it file-based and local:
  - Place JSON in `packages/web/public/reactflow.json` (or pass a local URL).
  - Fetch on page load and feed to `<ReactFlow />`.
- No backend required for the first pass.

### Data Extraction (SQLite)
1. Open DB file directly (no running server).
2. Introspect schema: confirm table names (`dominial_documento`, `dominial_lancamento`, `dominial_documentotipo`, `dominial_cartorios`, etc.).
3. Query root document:
   - If `--documento-id`, start there.
   - If `--imovel-id`, use the document that represents the **current property** (the one created at chain start and tied to `imovel.matricula`). Do **not** choose by date or global numeric order across cartórios.
4. Build graph edges using `dominial_lancamento.documento_origem` → `dominial_lancamento.documento` as chain links.
5. Join supporting fields for labels (document number, type, cartório, dates, etc.).

### Graph Mapping (React Flow)
- **Node** = Documento
  - `id`: `doc-${documento.id}`
  - `data`: `{ numero, tipo, cartorio, data, livro, folha, origem, lancamentosCount, ... }`
- **Edge** = Lancamento (especially `inicio_matricula`) that links to an origin document
  - `id`: `lanc-${lancamento.id}`
  - `source`: `doc-${documento_origem_id}`
  - `target`: `doc-${documento_id}`

### Layout (simple, deterministic)
- First pass: BFS from root, assign `depth`.
- Positioning rule:
  - `x = depth * 300`
  - `y = indexWithinLevel * 120`
- This gives a readable left-to-right tree without external layout libs.
- Optionally add a `--layout dagre` flag later.

### Multi-origin / end-of-chain handling
- If a `Lancamento` has multiple origins (legacy uses `OrigemFimCadeia.indice_origem`), decide:
  - **Decision:** Include all origin edges (DAG, not a strict tree).
  - Apply ordering rule for origins where needed (matricula desc, then transcricao desc).
- For end-of-chain markers:
  - **Decision:** “Fim de cadeia” is a special **lancamento** type; create a synthetic “fim de cadeia” node as an absolute leaf.
  - Edge from the document to this leaf node; no outgoing edges from the leaf.
  - Include `classificacao_fim_cadeia` and `tipo_fim_cadeia` in node data.

### Graph semantics (DAG, not a strict tree)
- The chain is a directed acyclic graph (DAG); nodes can have multiple origins.
- Hierarchical depth is contextual, not authoritative.
- Origin identity can reconcile a node to an ancestor’s level.
- The layout should remain stable without duplicating nodes; edges capture multiple relations.

### Modularity + Reuse (for fullstack later)
- Organize the script as reusable modules to be dropped into `packages/api` and `packages/web` later.
- Proposed module boundaries:
  - `db/` (SQLite access + typed query helpers)
  - `domain/` (Documento/Lancamento shapes)
  - `graph/` (build nodes/edges, end-of-chain handling, multi-origin handling)
  - `layout/` (BFS layout and level computation)
  - `io/` (JSON read/write, CLI parsing)
- Keep all pure logic functions side-effect free to ease testing and reuse.

### Test Plan (Vitest, 100% unit coverage for logic)
- Use **Vitest** for pure logic modules (`domain`, `graph`, `layout`).
- Tests must cover:
  - Root selection rules (documento principal).
  - Parsing origins and building edges.
  - Multi-origin handling behavior (DAG edges, ordering).
  - End-of-chain synthetic nodes.
  - Level computation and layout stability (visual positioning only).
  - Cycle prevention (visited set) to avoid infinite loops.

### Logic Inspiration (legacy docs)
- Use the D3 flow docs as the reference for the core graph logic and levels (consolidated into `docs/domain/` as part of the T-403 doc rename):
  - `docs/domain/visualization-d3.md`
  - `docs/domain/visualization-d3-analysis.md`
  - `docs/domain/visualization-d3-reference.md`

## Implementation Steps
1. **Schema recon**: Write a small script to list tables + sample columns via `PRAGMA table_info` to confirm names.
2. **Query design**:
   - Fetch document + document type + cartório.
   - Fetch all `Lancamento` for these documents, including `documento_origem`.
3. **Graph build**:
   - Create a `Map` of documents to nodes.
   - For each `Lancamento` with `documento_origem`, add edge.
   - Add synthetic end-of-chain nodes when needed.
4. **Layout**:
   - Build adjacency (source → target).
   - BFS from root and assign positions.
5. **Output**:
   - Serialize `{ nodes, edges }` to JSON.
6. **React + Vite viewer**:
   - Scaffold minimal `packages/web` app.
   - Fetch `reactflow.json` from `public/`.
   - Render with React Flow and `fitView`.
7. **Unit tests (Vitest)**:
   - Add tests for all pure modules and hit 100% coverage for graph/layout logic.

## Open Questions (need user input)
1. Root selection: **Use the latest registry number**, not date. Root is the document representing the most recent registry (usually `numero == imovel.matricula`). If not found, choose the document with the highest registry number (matricula/transcricao numeric) within the imóvel.
2. Lancamentos: **Do not appear on the graph**; they only supply origin data for edges.
3. Cycle handling: **Assume cycles should not exist**; if detected, treat as data error (log and skip the edge) and continue.

## Minimal Success Criteria
- Script runs locally, opens `./sqlite3.sql`, and outputs `reactflow.json`.
- JSON is loadable by React Flow with visible nodes and edges.
- Minimal React + Vite app renders the exported JSON without a backend.
- Core graph/layout logic is fully unit-tested (100% coverage).
