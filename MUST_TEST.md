# MUST_TEST

## Frontend (packages/web)
- Lazy-loaded route: `packages/web/src/router.tsx` wraps `GraphRoute` with `React.lazy` but no `Suspense` boundary is present; add tests for the `/graph` route to verify a loading fallback renders and the route resolves without crashing.
- Graph page render: `packages/web/src/routes/graph.tsx` should render the graph shell, nodes, and controls; add a test that `ReactFlow` mounts and `fitView` does not throw (mock if needed).

## Configuration
- Workspace install sanity: add a CI or local script check that `pnpm install` and `pnpm build` complete on a clean machine.
