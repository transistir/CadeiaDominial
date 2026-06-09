import type { GraphJson } from "./types";

/**
 * Re-export the chain-topology generator so the web app can import it
 * from `@cadeia/web/src/graph` (or via the package barrel `index.ts`).
 * The implementation lives in `@cadeia/chain-topology` (scripts/seed);
 * the web package depends on it via the workspace protocol.
 */
export {
  generateChainTopology,
  assertTopologyInvariants,
  TopologyInvariantError,
  type TopologyGraph,
  type TopologyImovel,
  type TopologyImovelDocumento,
  type TopologyDocumento,
  type TopologyLancamento,
  type TopologyOrigem,
  type TopologyFimCadeia,
  type ChainShape,
  type GenerateChainTopologyOptions,
} from "@cadeia/chain-topology";

import type { TopologyGraph } from "@cadeia/chain-topology";
import { toGraphJson as seedToGraphJson } from "@cadeia/chain-topology";
import { validateGraph } from "./validateGraph";

/**
 * Convert a `TopologyGraph` (the rich seed-script output) into the minimal
 * `GraphJson` shape consumed by `validateGraph`, `layoutGraph`, and
 * `GraphPreview`. Validates the converted output via `validateGraph` so
 * that callers receive a graph guaranteed to be renderable; throws
 * `Error` (from `validateGraph`) on structural issues with the converted
 * graph (duplicate node/edge ids, edges referencing missing nodes, etc.).
 * Callers who want the deeper `assertTopologyInvariants` checks (DAG,
 * contiguity, terminal fims, weak connectivity, S-3/Q13) should run
 * `assertTopologyInvariants(top)` separately — those throw
 * `TopologyInvariantError` and are NOT triggered by this function.
 */
export function topologyToGraphJson(top: TopologyGraph): GraphJson {
  const json = seedToGraphJson(top) as GraphJson;
  return validateGraph(json);
}
