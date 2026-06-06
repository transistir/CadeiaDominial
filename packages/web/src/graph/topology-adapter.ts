import type { GraphJson } from "./types";

/**
 * Re-export the chain-topology generator so the web app can import it
 * from `@cadeia/web/src/graph` (or via the package barrel `index.ts`).
 * The implementation lives in `scripts/seed/chain-topology.ts`; the web
 * package depends on the same source via a relative path. Keeping the
 * implementation in `scripts/seed/` means the seed script and its tests
 * own the contract, and the web package is a thin consumer.
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
} from "../../../../scripts/seed/chain-topology";

import type { TopologyGraph } from "../../../../scripts/seed/chain-topology";
import { toGraphJson as seedToGraphJson } from "../../../../scripts/seed/chain-topology";

/**
 * Convert a `TopologyGraph` (the rich seed-script output) into the minimal
 * `GraphJson` shape consumed by `validateGraph`, `layoutGraph`, and
 * `GraphPreview`. The seed module's `toGraphJson` does the same conversion
 * with a structural type; this wrapper exposes it under the canonical
 * `GraphJson` name from `packages/web/src/graph/types.ts` and lets web
 * consumers stay decoupled from the seed module's internal type.
 */
export function topologyToGraphJson(top: TopologyGraph): GraphJson {
  return seedToGraphJson(top) as GraphJson;
}
