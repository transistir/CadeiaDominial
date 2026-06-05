# `screenshots/`

Regression-baseline PNGs for the `pnpm graph:screenshot` command.

## Files

| File | Source | Purpose |
|------|--------|---------|
| `basic-graph.png` | `pnpm graph:screenshot` | 1280×720 rendering of `packages/web/src/graph/fixtures/basic-graph.json` via React Flow. |

## When to regenerate

- After changing `packages/web/src/graph/` (types, validation, layout, adapter, or
  renderer).
- After bumping `@xyflow/react` — its internal styling or rendering can shift
  the visual.
- After changing the React Flow `Background` / `fitView` settings in
  `GraphPreview.tsx`.

## How to regenerate

```bash
pnpm install         # if node_modules is missing
pnpm graph:screenshot
```

The new PNG overwrites `basic-graph.png`. Review the diff (e.g. open the new
PNG against the old one in any image viewer) and commit the new baseline if
the change is intentional.

## What this is NOT

- **Not** a CI artifact — it's committed to the repo on purpose, so a clean
  clone has the baseline without running the screenshot pipeline.
- **Not** a snapshot test — Playwright does not byte-compare the PNG in CI.
  Visual review on regeneration is the contract.
- **Not** a build cache — anything larger or generated-by-build belongs in
  `node_modules` / `dist`, not here.
