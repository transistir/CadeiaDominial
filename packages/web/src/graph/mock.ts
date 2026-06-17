import type { GraphJson } from "./types";
import { validateGraph } from "./validateGraph";

/**
 * Shape parameter for `generateMockGraph`.
 * Determines the structure of the generated chain.
 */
export type MockShape = "linear" | "branching" | "merge" | "complex";

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
  if (shape === "merge") {
    return generateMerge();
  }
  return generateComplex();
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

function generateComplex(): GraphJson {
  const graph: GraphJson = {
    nodes: [
      {
        id: "doc-01",
        label: "Documento M1",
        type: "documento",
        data: { numero: "M1", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-01" },
      },
      {
        id: "doc-02",
        label: "Documento M2",
        type: "documento",
        data: { numero: "M2", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-02" },
      },
      {
        id: "doc-03",
        label: "Documento T1",
        type: "documento",
        data: { numero: "T1", tipo: "transcricao", cartorioId: "cartorio-1", data: "2024-01-03" },
      },
      {
        id: "doc-04",
        label: "Documento M4",
        type: "documento",
        data: { numero: "M4", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-04" },
      },
      {
        id: "doc-05",
        label: "Documento T2",
        type: "documento",
        data: { numero: "T2", tipo: "transcricao", cartorioId: "cartorio-1", data: "2024-01-05" },
      },
      {
        id: "doc-06",
        label: "Documento M6",
        type: "documento",
        data: { numero: "M6", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-06" },
      },
      {
        id: "doc-07",
        label: "Documento M7",
        type: "documento",
        data: { numero: "M7", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-07" },
      },
      {
        id: "doc-08",
        label: "Documento T3",
        type: "documento",
        data: { numero: "T3", tipo: "transcricao", cartorioId: "cartorio-1", data: "2024-01-08" },
      },
      {
        id: "doc-09",
        label: "Documento M9",
        type: "documento",
        data: { numero: "M9", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-09" },
      },
      {
        id: "doc-10",
        label: "Documento T4",
        type: "documento",
        data: { numero: "T4", tipo: "transcricao", cartorioId: "cartorio-1", data: "2024-01-10" },
      },
      {
        id: "doc-11",
        label: "Documento M11",
        type: "documento",
        data: { numero: "M11", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-11" },
      },
      {
        id: "doc-12",
        label: "Documento T5",
        type: "documento",
        data: { numero: "T5", tipo: "transcricao", cartorioId: "cartorio-1", data: "2024-01-12" },
      },
      {
        id: "doc-13",
        label: "Documento M13",
        type: "documento",
        data: { numero: "M13", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-13" },
      },
      {
        id: "doc-14",
        label: "Documento T6",
        type: "documento",
        data: { numero: "T6", tipo: "transcricao", cartorioId: "cartorio-1", data: "2024-01-14" },
      },
      {
        id: "doc-15",
        label: "Documento M15",
        type: "documento",
        data: { numero: "M15", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-15" },
      },
      {
        id: "doc-16",
        label: "Documento T7",
        type: "documento",
        data: { numero: "T7", tipo: "transcricao", cartorioId: "cartorio-1", data: "2024-01-16" },
      },
      {
        id: "fim-11",
        label: "Fim de cadeia",
        type: "fimCadeia",
        data: { classificacao: "inconclusa" },
      },
      {
        id: "fim-12",
        label: "Fim de cadeia",
        type: "fimCadeia",
        data: { classificacao: "origem_lidima" },
      },
      {
        id: "fim-13",
        label: "Fim de cadeia",
        type: "fimCadeia",
        data: { classificacao: "sem_origem" },
      },
      {
        id: "fim-14",
        label: "Fim de cadeia",
        type: "fimCadeia",
        data: { classificacao: "inconclusa" },
      },
      {
        id: "fim-16",
        label: "Fim de cadeia",
        type: "fimCadeia",
        data: { classificacao: "sem_origem" },
      },
    ],
    edges: [
      { id: "orig-1", source: "doc-01", target: "doc-02", data: { tipoOrigem: "matricula" } },
      { id: "orig-2", source: "doc-02", target: "doc-03", data: { tipoOrigem: "matricula" } },
      { id: "orig-3", source: "doc-03", target: "doc-04", data: { tipoOrigem: "transcricao" } },
      { id: "orig-4", source: "doc-04", target: "doc-05", data: { tipoOrigem: "matricula" } },
      { id: "orig-5", source: "doc-05", target: "doc-06", data: { tipoOrigem: "transcricao" } },
      { id: "orig-6", source: "doc-06", target: "doc-07", data: { tipoOrigem: "matricula" } },
      { id: "orig-7", source: "doc-07", target: "doc-08", data: { tipoOrigem: "matricula" } },
      { id: "orig-8", source: "doc-08", target: "doc-09", data: { tipoOrigem: "transcricao" } },
      { id: "orig-9", source: "doc-09", target: "doc-10", data: { tipoOrigem: "matricula" } },
      { id: "orig-10", source: "doc-10", target: "doc-11", data: { tipoOrigem: "transcricao" } },
      { id: "doc-11->fim-11", source: "doc-11", target: "fim-11", data: { tipoOrigem: "fim_cadeia" } },
      { id: "orig-12", source: "doc-03", target: "doc-12", data: { tipoOrigem: "transcricao" } },
      { id: "doc-12->fim-12", source: "doc-12", target: "fim-12", data: { tipoOrigem: "fim_cadeia" } },
      { id: "orig-13", source: "doc-05", target: "doc-13", data: { tipoOrigem: "transcricao" } },
      { id: "doc-13->fim-13", source: "doc-13", target: "fim-13", data: { tipoOrigem: "fim_cadeia" } },
      { id: "orig-14", source: "doc-07", target: "doc-14", data: { tipoOrigem: "matricula" } },
      { id: "doc-14->fim-14", source: "doc-14", target: "fim-14", data: { tipoOrigem: "fim_cadeia" } },
      { id: "orig-15", source: "doc-09", target: "doc-15", data: { tipoOrigem: "matricula" } },
      { id: "orig-16", source: "doc-15", target: "doc-16", data: { tipoOrigem: "matricula" } },
      { id: "doc-16->fim-16", source: "doc-16", target: "fim-16", data: { tipoOrigem: "fim_cadeia" } },
    ],
  };

  return validateGraph(graph);
}
