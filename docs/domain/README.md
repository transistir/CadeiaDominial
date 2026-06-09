# Domain — Cadeia Dominial

Documents describing **what a land-registry chain is** in this system. Independent of any specific technology stack; the same concepts apply to the legacy Django implementation and the v2 TypeScript rewrite.

## Reading order

1. [`overview.md`](./overview.md) — Quick orientation (37L, 2-minute read)
2. [`lancamento-tipos.md`](./lancamento-tipos.md) — All types of "lançamentos" (registrations) on a property
3. [`tree-model.md`](./tree-model.md) — How properties form trees via transmissões
4. [`fim-de-cadeia.md`](./fim-de-cadeia.md) — End-of-chain semantics
5. [`visualization-d3.md`](./visualization-d3.md) — Full D3 chain visualization flow
6. [`visualization-d3-reference.md`](./visualization-d3-reference.md) — D3 technical reference
7. [`visualization-d3-analysis.md`](./visualization-d3-analysis.md) — D3 documentation-vs-code analysis
8. [`react-flow-quick-reference.md`](./react-flow-quick-reference.md) — React Flow quick reference for the v2 UI

## Migration note

The D3 documents describe the **legacy Django** visualization. The v2 frontend uses **React Flow** instead — see [`react-flow-quick-reference.md`](./react-flow-quick-reference.md) and the [migration guide](../MIGRATION_GUIDE.md) and [`ARCHITECTURE_DECISIONS.md`](../ARCHITECTURE_DECISIONS.md) for the rationale.
