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
 * `TopologyInvariantError` (re-exported from the seed module) if the
 * topology violates structural invariants the validator checks. Run
 * `assertTopologyInvariants(top)` first if you want the deeper
 * structural checks (DAG, contiguity, terminal fims) before converting.
 */
export function topologyToGraphJson(top: TopologyGraph): GraphJson {
  const json = seedToGraphJson(top) as GraphJson;
  return validateGraph(json);
}
