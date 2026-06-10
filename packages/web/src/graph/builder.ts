import type { LancamentoTipo } from "@cadeia/chain-topology";
import type { DocumentoTipo, GraphEdge, GraphJson, GraphNode, OrigemTipo } from "./types";
import { validateGraph } from "./validateGraph";

/**
 * Minimal typed domain input for `buildGraph`. This is a simplified shape
 * compared to `TopologyGraph` — it's designed for API responses or direct
 * user-provided data, not the rich seed-script output.
 */
export interface ChainData {
  documentos: Array<{
    id: string;
    numero: string;
    tipo: DocumentoTipo;
    cartorioId: string;
    data: string;
  }>;
  lancamentos: Array<{
    id: string;
    documentoId: string;
    tipo: LancamentoTipo;
  }>;
  origens: Array<{
    id: string;
    lancamentoId: string;
    documentoId: string;
    tipoOrigem?: OrigemTipo;
  }>;
}

/**
 * Builds a `{ nodes, edges }` graph from typed domain input.
 *
 * - Maps documentos → nodes with `type: "documento"`
 * - Maps origens → edges from source documento → target documento
 * - Adds synthetic `fim-cadeia` leaves for documentos with no outgoing origens
 * - Calls `validateGraph()` before returning (defense in depth)
 *
 * Throws on invalid input (missing documento/lancamento references, cycles, etc.).
 */
export function buildGraph(chainData: ChainData): GraphJson {
  const lancamentosById = new Map(chainData.lancamentos.map((l) => [l.id, l]));
  const documentosById = new Map(chainData.documentos.map((d) => [d.id, d]));

  const nodes: GraphNode[] = chainData.documentos.map((doc) => {
    const id = ensureDocPrefix(doc.id);
    return {
      id,
      label: `Documento ${doc.numero}`,
      type: "documento",
      data: {
        numero: doc.numero,
        tipo: doc.tipo,
        cartorioId: doc.cartorioId,
        data: doc.data,
      },
    };
  });

  const edges: GraphEdge[] = [];

  // Track which documentos are sources of at least one origem
  const documentosAsSource = new Set<string>();

  for (const origem of chainData.origens) {
    const lancamento = lancamentosById.get(origem.lancamentoId);
    if (!lancamento) {
      throw new Error(`Origem ${origem.id} references non-existent lancamento: ${origem.lancamentoId}`);
    }

    const targetDoc = documentosById.get(lancamento.documentoId);
    if (!targetDoc) {
      throw new Error(
        `Lancamento ${lancamento.id} references non-existent documento: ${lancamento.documentoId}`
      );
    }

    const sourceDoc = documentosById.get(origem.documentoId);
    if (!sourceDoc) {
      throw new Error(`Origem ${origem.id} references non-existent documento: ${origem.documentoId}`);
    }

    const sourceId = ensureDocPrefix(origem.documentoId);
    const targetId = ensureDocPrefix(lancamento.documentoId);

    documentosAsSource.add(sourceId);

    edges.push({
      id: origem.id,
      source: sourceId,
      target: targetId,
      data: {
        tipoOrigem:
          origem.tipoOrigem ?? inferOrigemTipo(sourceDoc.tipo),
      },
    });
  }

  // Add synthetic fim-cadeia leaves for documentos with no outgoing origens
  for (const doc of chainData.documentos) {
    const docId = ensureDocPrefix(doc.id);
    if (!documentosAsSource.has(docId)) {
      const fimId = `fim-${doc.id}`;
      nodes.push({
        id: fimId,
        label: "Fim de cadeia",
        type: "fimCadeia",
        data: { classificacao: "inconclusa" },
      });
      edges.push({
        id: `synthetic-${docId}->${fimId}`,
        source: docId,
        target: fimId,
        data: { tipoOrigem: "fim_cadeia" },
      });
    }
  }

  return validateGraph({ nodes, edges });
}

/**
 * Ensures a documento ID has the `doc-` prefix.
 * If it already has the prefix, returns it unchanged.
 */
function ensureDocPrefix(id: string): string {
  return id.startsWith("doc-") ? id : `doc-${id}`;
}

/**
 * Infers `OrigemTipo` from a documento's tipo.
 *
 * Follows the convention from `topology-adapter.ts`:
 * - transcricao → "transcricao"
 * - matricula or averbacao → "matricula" (averbacao coerces to matricula)
 * TODO: Revisit this coercion — averbacao may need distinct handling
 */
function inferOrigemTipo(sourceDocTipo: DocumentoTipo): OrigemTipo {
  return sourceDocTipo === "transcricao" ? "transcricao" : "matricula";
}
