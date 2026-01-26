# MUST_TEST

## Frontend (packages/web)
- Lazy-loaded route: `packages/web/src/router.tsx` wraps `GraphRoute` with `React.lazy` but no `Suspense` boundary is present; add tests for the `/graph` route to verify a loading fallback renders and the route resolves without crashing.
- Graph page render: `packages/web/src/routes/graph.tsx` should render the graph shell, nodes, and controls; add a test that `ReactFlow` mounts and `fitView` does not throw (mock if needed).

## Build / Bundling
- Chunking config: `packages/web/vite.config.ts` manualChunks definitions should not regress build output; add a build verification test or script that asserts `react-vendor`, `router`, `query`, and `react-flow` chunks are produced.

## Configuration
- Workspace config: `pnpm-workspace.yaml` now ignores `esbuild`, `sharp`, `workerd`; add a sanity check to ensure installs still succeed and required binaries are present in CI.
