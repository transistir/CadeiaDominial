import type { GraphJson } from "./types";
import { validateGraph } from "./validateGraph";

/**
 * Shape parameter for `generateMockGraph`.
 * Determines the structure of the generated chain.
 */
export type MockShape = "linear" | "branching" | "merge";

/**
 * Generates a deterministic mock graph for development.
 *
 * - **Linear**: 5 documentos in a chain with 1 synthetic fim leaf
 * - **Branching**: 1 root → 2 branches → 2 separate synthetic fim leaves
 * - **Merge**: 2 sources merge into 1 target → 1 synthetic fim leaf
 *
 * Uses pure construction (no PRNG) — same shape → byte-identical output every time.
 * Calls `validateGraph()` before returning (defense in depth).
 */
export function generateMockGraph(shape: MockShape): GraphJson {
  if (shape === "linear") {
    return generateLinear();
  }
  if (shape === "branching") {
    return generateBranching();
  }
  return generateMerge();
}

function generateLinear(): GraphJson {
  const graph: GraphJson = {
    nodes: [
      {
        id: "doc-1",
        label: "Documento M1",
        type: "documento",
        // TODO(T-503): real cartório lookup; placeholder until multi-cartório
        // support lands.
        data: { numero: "M1", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-01" },
      },
      {
        id: "doc-2",
        label: "Documento M2",
        type: "documento",
        data: { numero: "M2", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-02" },
      },
      {
        id: "doc-3",
        label: "Documento M3",
        type: "documento",
        data: { numero: "M3", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-03" },
      },
      {
        id: "doc-4",
        label: "Documento M4",
        type: "documento",
        data: { numero: "M4", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-04" },
      },
      {
        id: "doc-5",
        label: "Documento M5",
        type: "documento",
        data: { numero: "M5", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-05" },
      },
      {
        id: "fim-5",
        label: "Fim de cadeia",
        type: "fimCadeia",
        data: { classificacao: "inconclusa" },
      },
    ],
    edges: [
      { id: "orig-1", source: "doc-1", target: "doc-2", data: { tipoOrigem: "matricula" } },
      { id: "orig-2", source: "doc-2", target: "doc-3", data: { tipoOrigem: "matricula" } },
      { id: "orig-3", source: "doc-3", target: "doc-4", data: { tipoOrigem: "matricula" } },
      { id: "orig-4", source: "doc-4", target: "doc-5", data: { tipoOrigem: "matricula" } },
      { id: "doc-5->fim-5", source: "doc-5", target: "fim-5", data: { tipoOrigem: "fim_cadeia" } },
    ],
  };

  return validateGraph(graph);
}

function generateBranching(): GraphJson {
  const graph: GraphJson = {
    nodes: [
      {
        id: "doc-1",
        label: "Documento M1",
        type: "documento",
        data: { numero: "M1", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-01" },
      },
      {
        id: "doc-2",
        label: "Documento M2",
        type: "documento",
        data: { numero: "M2", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-02" },
      },
      {
        id: "doc-3",
        label: "Documento T1",
        type: "documento",
        data: { numero: "T1", tipo: "transcricao", cartorioId: "cartorio-1", data: "2024-01-03" },
      },
      {
        id: "doc-4",
        label: "Documento M4",
        type: "documento",
        data: { numero: "M4", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-04" },
      },
      {
        id: "fim-3",
        label: "Fim de cadeia",
        type: "fimCadeia",
        data: { classificacao: "origem_lidima" },
      },
      {
        id: "fim-4",
        label: "Fim de cadeia",
        type: "fimCadeia",
        data: { classificacao: "sem_origem" },
      },
    ],
    edges: [
      { id: "orig-1", source: "doc-1", target: "doc-2", data: { tipoOrigem: "matricula" } },
      { id: "orig-2", source: "doc-2", target: "doc-3", data: { tipoOrigem: "matricula" } },
      { id: "orig-3", source: "doc-2", target: "doc-4", data: { tipoOrigem: "matricula" } },
      { id: "doc-3->fim-3", source: "doc-3", target: "fim-3", data: { tipoOrigem: "fim_cadeia" } },
      { id: "doc-4->fim-4", source: "doc-4", target: "fim-4", data: { tipoOrigem: "fim_cadeia" } },
    ],
  };

  return validateGraph(graph);
}

function generateMerge(): GraphJson {
  const graph: GraphJson = {
    nodes: [
      {
        id: "doc-1",
        label: "Documento M1",
        type: "documento",
        data: { numero: "M1", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-01" },
      },
      {
        id: "doc-2",
        label: "Documento T1",
        type: "documento",
        data: { numero: "T1", tipo: "transcricao", cartorioId: "cartorio-1", data: "2024-01-02" },
      },
      {
        id: "doc-3",
        label: "Documento M3",
        type: "documento",
        data: { numero: "M3", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-03" },
      },
      {
        id: "fim-3",
        label: "Fim de cadeia",
        type: "fimCadeia",
        data: { classificacao: "inconclusa" },
      },
    ],
    edges: [
      { id: "orig-1", source: "doc-1", target: "doc-3", data: { tipoOrigem: "matricula" } },
      { id: "orig-2", source: "doc-2", target: "doc-3", data: { tipoOrigem: "transcricao" } },
      { id: "doc-3->fim-3", source: "doc-3", target: "fim-3", data: { tipoOrigem: "fim_cadeia" } },
    ],
  };

  return validateGraph(graph);
}
