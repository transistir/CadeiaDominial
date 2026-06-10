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
  type GenerateChainTopologyOptions
} from "@cadeia/chain-topology";

import type { TopologyDocumento, TopologyGraph, TopologyLancamento } from "@cadeia/chain-topology";
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
  assertNoTopologyNodeIdCollisions(top);

  const documentosById = new Map<string, TopologyDocumento>();
  for (const doc of top.documentos) {
    documentosById.set(doc.id, doc);
  }

  const lancamentosById = new Map<string, TopologyLancamento>();
  for (const lanc of top.lancamentos) {
    lancamentosById.set(lanc.id, lanc);
  }

  const origemById = new Map(top.origens.map((origem) => [origem.id, origem]));

  const json: GraphJson = {
    nodes: [
      ...top.documentos.map((doc) => {
        const idx = doc.id.replace(/^doc-/, "");
        const tipo = toDocumentoTipo(doc);
        const numeroPrefix = tipo === "transcricao" ? "T" : "M";

        return {
          id: doc.id,
          label: `Documento ${idx}`,
          type: "documento" as const,
          data: {
            numero: `${numeroPrefix}${idx}`,
            tipo,
            cartorioId: "cartorio-1",
            data: "2024-01-01"
          }
        };
      }),
      ...top.fimCadeias.map((fim) => ({
        id: fim.id,
        label: "Fim de cadeia",
        type: "fimCadeia" as const,
        data: { classificacao: "inconclusa" as const }
      }))
    ],
    edges: [
      ...top.origens.flatMap((origem) => {
        const lancamento = lancamentosById.get(origem.lancamentoId);
        if (!lancamento) {
          return [];
        }

        const sourceDoc = documentosById.get(origem.documentoId);
        return [
          {
            id: origem.id,
            source: origem.documentoId,
            target: lancamento.documentoId,
            data: {
              tipoOrigem: toOrigemTipo(sourceDoc)
            }
          }
        ];
      }),
      ...top.fimCadeias.flatMap((fim) => {
        const origem = origemById.get(fim.origemId);
        if (!origem) {
          return [];
        }
        const lancamento = lancamentosById.get(origem.lancamentoId);
        if (!lancamento) {
          return [];
        }

        return [
          {
            id: `${lancamento.documentoId}->${fim.id}`,
            source: lancamento.documentoId,
            target: fim.id,
            data: { tipoOrigem: "fim_cadeia" as const }
          }
        ];
      })
    ]
  };

  return validateGraph(json);
}

function assertNoTopologyNodeIdCollisions(top: TopologyGraph): void {
  const nodeIds = new Set<string>();

  for (const doc of top.documentos) {
    addTopologyNodeId(nodeIds, doc.id, "documento");
  }
  for (const lanc of top.lancamentos) {
    addTopologyNodeId(nodeIds, lanc.id, "lancamento");
  }
  for (const fim of top.fimCadeias) {
    addTopologyNodeId(nodeIds, fim.id, "fim_cadeia");
  }
}

function addTopologyNodeId(ids: Set<string>, id: string, collection: string): void {
  if (ids.has(id)) {
    throw new Error(`Topology node id collision: ${id} (${collection})`);
  }
  ids.add(id);
}

function toDocumentoTipo(doc: TopologyDocumento): "matricula" | "transcricao" {
  return doc.tipo === "transcricao" ? "transcricao" : "matricula";
}

function toOrigemTipo(doc: TopologyDocumento | undefined): "matricula" | "transcricao" {
  return doc?.tipo === "transcricao" ? "transcricao" : "matricula";
}
