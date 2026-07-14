import { describe, it, expect } from "vitest";
import { buildGraph, type ChainData } from "./builder";
import type { LancamentoTipo } from "@cadeia/chain-topology";

describe("buildGraph", () => {
  // --- Happy paths (3 cases) ---

  it("single documento with no origens → adds synthetic fim-cadeia leaf", () => {
    const chainData: ChainData = {
      documentos: [
        {
          id: "1",
          numero: "M1",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-01",
        },
      ],
      lancamentos: [],
      origens: [],
    };

    const result = buildGraph(chainData);

    expect(result.nodes).toHaveLength(2);
    expect(result.nodes[0].id).toBe("doc-1");
    expect(result.nodes[0].type).toBe("documento");
    expect(result.nodes[1].id).toBe("fim-1");
    expect(result.nodes[1].type).toBe("fimCadeia");
    const fimNode = result.nodes[1];
    if (fimNode.type === "fimCadeia") {
      expect(fimNode.data.classificacao).toBe("inconclusa");
    }

    expect(result.edges).toHaveLength(1);
    expect(result.edges[0].source).toBe("doc-1");
    expect(result.edges[0].target).toBe("fim-1");
    expect(result.edges[0].data?.tipoOrigem).toBe("fim_cadeia");
  });

  it("linear chain of 3 documentos → correct edges + synthetic leaf on last", () => {
    const chainData: ChainData = {
      documentos: [
        {
          id: "1",
          numero: "M1",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-01",
        },
        {
          id: "2",
          numero: "M2",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-02",
        },
        {
          id: "3",
          numero: "M3",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-03",
        },
      ],
      lancamentos: [
        { id: "lanc-1", documentoId: "2", tipo: "registro" as LancamentoTipo },
        { id: "lanc-2", documentoId: "3", tipo: "registro" as LancamentoTipo },
      ],
      origens: [
        { id: "orig-1", lancamentoId: "lanc-1", documentoId: "1" },
        { id: "orig-2", lancamentoId: "lanc-2", documentoId: "2" },
      ],
    };

    const result = buildGraph(chainData);

    expect(result.nodes).toHaveLength(4);
    expect(result.nodes.map((n) => n.id)).toEqual(["doc-1", "doc-2", "doc-3", "fim-3"]);

    expect(result.edges).toHaveLength(3);
    expect(result.edges[0].source).toBe("doc-1");
    expect(result.edges[0].target).toBe("doc-2");
    expect(result.edges[1].source).toBe("doc-2");
    expect(result.edges[1].target).toBe("doc-3");
    expect(result.edges[2].source).toBe("doc-3");
    expect(result.edges[2].target).toBe("fim-3");
  });

  it("branching (1→2) → both branches get synthetic leaves", () => {
    const chainData: ChainData = {
      documentos: [
        {
          id: "1",
          numero: "M1",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-01",
        },
        {
          id: "2",
          numero: "M2",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-02",
        },
        {
          id: "3",
          numero: "M3",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-03",
        },
      ],
      lancamentos: [
        { id: "lanc-1", documentoId: "2", tipo: "registro" as LancamentoTipo },
        { id: "lanc-2", documentoId: "3", tipo: "registro" as LancamentoTipo },
      ],
      origens: [
        { id: "orig-1", lancamentoId: "lanc-1", documentoId: "1" },
        { id: "orig-2", lancamentoId: "lanc-2", documentoId: "1" },
      ],
    };

    const result = buildGraph(chainData);

    expect(result.nodes).toHaveLength(5);
    expect(result.nodes.map((n) => n.id)).toEqual([
      "doc-1",
      "doc-2",
      "doc-3",
      "fim-2",
      "fim-3",
    ]);

    expect(result.edges).toHaveLength(4);
    expect(result.edges[0].source).toBe("doc-1");
    expect(result.edges[0].target).toBe("doc-2");
    expect(result.edges[1].source).toBe("doc-1");
    expect(result.edges[1].target).toBe("doc-3");
    expect(result.edges[2].source).toBe("doc-2");
    expect(result.edges[2].target).toBe("fim-2");
    expect(result.edges[3].source).toBe("doc-3");
    expect(result.edges[3].target).toBe("fim-3");
  });

  it("diamond DAG (1→2, 1→3, 2→4, 3→4) → does not report a cycle", () => {
    const chainData: ChainData = {
      documentos: [
        {
          id: "1",
          numero: "M1",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-01",
        },
        {
          id: "2",
          numero: "M2",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-02",
        },
        {
          id: "3",
          numero: "M3",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-03",
        },
        {
          id: "4",
          numero: "M4",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-04",
        },
      ],
      lancamentos: [
        { id: "lanc-1", documentoId: "2", tipo: "registro" as LancamentoTipo },
        { id: "lanc-2", documentoId: "3", tipo: "registro" as LancamentoTipo },
        { id: "lanc-3", documentoId: "4", tipo: "registro" as LancamentoTipo },
        { id: "lanc-4", documentoId: "4", tipo: "registro" as LancamentoTipo },
      ],
      origens: [
        { id: "orig-1", lancamentoId: "lanc-1", documentoId: "1" },
        { id: "orig-2", lancamentoId: "lanc-2", documentoId: "1" },
        { id: "orig-3", lancamentoId: "lanc-3", documentoId: "2" },
        { id: "orig-4", lancamentoId: "lanc-4", documentoId: "3" },
      ],
    };

    const result = buildGraph(chainData);

    expect(result.nodes.map((n) => n.id)).toEqual([
      "doc-1",
      "doc-2",
      "doc-3",
      "doc-4",
      "fim-4",
    ]);
  });

  // --- Edge mapping (3 cases + MUST-FIX #2) ---

  it("edge with tipoOrigem provided → uses provided value", () => {
    const chainData: ChainData = {
      documentos: [
        {
          id: "1",
          numero: "M1",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-01",
        },
        {
          id: "2",
          numero: "M2",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-02",
        },
      ],
      lancamentos: [
        { id: "lanc-1", documentoId: "2", tipo: "registro" as LancamentoTipo },
      ],
      origens: [
        {
          id: "orig-1",
          lancamentoId: "lanc-1",
          documentoId: "1",
          tipoOrigem: "transcricao",
        },
      ],
    };

    const result = buildGraph(chainData);

    expect(result.edges).toHaveLength(2);
    expect(result.edges[0].data?.tipoOrigem).toBe("transcricao");
  });

  it("edge without tipoOrigem from matricula source → infers as matricula", () => {
    const chainData: ChainData = {
      documentos: [
        {
          id: "1",
          numero: "M1",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-01",
        },
        {
          id: "2",
          numero: "M2",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-02",
        },
      ],
      lancamentos: [
        { id: "lanc-1", documentoId: "2", tipo: "registro" as LancamentoTipo },
      ],
      origens: [{ id: "orig-1", lancamentoId: "lanc-1", documentoId: "1" }],
    };

    const result = buildGraph(chainData);

    expect(result.edges[0].data?.tipoOrigem).toBe("matricula");
  });

  it("edge without tipoOrigem from transcricao source → infers as transcricao", () => {
    const chainData: ChainData = {
      documentos: [
        {
          id: "1",
          numero: "T1",
          tipo: "transcricao",
          cartorioId: "cartorio-1",
          data: "2024-01-01",
        },
        {
          id: "2",
          numero: "M2",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-02",
        },
      ],
      lancamentos: [
        { id: "lanc-1", documentoId: "2", tipo: "registro" as LancamentoTipo },
      ],
      origens: [{ id: "orig-1", lancamentoId: "lanc-1", documentoId: "1" }],
    };

    const result = buildGraph(chainData);

    expect(result.edges[0].data?.tipoOrigem).toBe("transcricao");
  });

  it("MUST-FIX #2: edge from averbacao source (no tipoOrigem) → coerces to matricula", () => {
    const chainData: ChainData = {
      documentos: [
        {
          id: "1",
          numero: "A1",
          tipo: "averbacao",
          cartorioId: "cartorio-1",
          data: "2024-01-01",
        },
        {
          id: "2",
          numero: "M2",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-02",
        },
      ],
      lancamentos: [
        { id: "lanc-1", documentoId: "2", tipo: "registro" as LancamentoTipo },
      ],
      origens: [{ id: "orig-1", lancamentoId: "lanc-1", documentoId: "1" }],
    };

    const result = buildGraph(chainData);

    expect(result.edges[0].data?.tipoOrigem).toBe("matricula");
  });

  it("multiple edges from same source documento → all edges correct", () => {
    const chainData: ChainData = {
      documentos: [
        {
          id: "1",
          numero: "M1",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-01",
        },
        {
          id: "2",
          numero: "M2",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-02",
        },
        {
          id: "3",
          numero: "M3",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-03",
        },
      ],
      lancamentos: [
        { id: "lanc-1", documentoId: "2", tipo: "registro" as LancamentoTipo },
        { id: "lanc-2", documentoId: "3", tipo: "registro" as LancamentoTipo },
      ],
      origens: [
        { id: "orig-1", lancamentoId: "lanc-1", documentoId: "1" },
        { id: "orig-2", lancamentoId: "lanc-2", documentoId: "1" },
      ],
    };

    const result = buildGraph(chainData);

    expect(result.edges).toHaveLength(4);
    expect(result.edges[0].source).toBe("doc-1");
    expect(result.edges[0].target).toBe("doc-2");
    expect(result.edges[1].source).toBe("doc-1");
    expect(result.edges[1].target).toBe("doc-3");
  });

  // --- ID prefix enforcement (2 cases) ---

  it("documento ID without doc- prefix → adds it automatically", () => {
    const chainData: ChainData = {
      documentos: [
        {
          id: "raw-id-123",
          numero: "M123",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-01",
        },
      ],
      lancamentos: [],
      origens: [],
    };

    const result = buildGraph(chainData);

    expect(result.nodes[0].id).toBe("doc-raw-id-123");
    expect(result.edges[0].source).toBe("doc-raw-id-123");
  });

  it("documento ID with doc- prefix → keeps it unchanged", () => {
    const chainData: ChainData = {
      documentos: [
        {
          id: "doc-1",
          numero: "M1",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-01",
        },
      ],
      lancamentos: [],
      origens: [],
    };

    const result = buildGraph(chainData);

    expect(result.nodes[0].id).toBe("doc-1");
  });

  it("synthetic fim node ID → has fim- prefix", () => {
    const chainData: ChainData = {
      documentos: [
        {
          id: "abc-123",
          numero: "M1",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-01",
        },
      ],
      lancamentos: [],
      origens: [],
    };

    const result = buildGraph(chainData);

    expect(result.nodes[1].id).toBe("fim-abc-123");
    expect(result.edges[0].target).toBe("fim-abc-123");
  });

  // --- Validation integration (2 cases) ---

  it("calls validateGraph() internally → returns valid GraphJson", () => {
    const chainData: ChainData = {
      documentos: [
        {
          id: "1",
          numero: "M1",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-01",
        },
      ],
      lancamentos: [],
      origens: [],
    };

    const result = buildGraph(chainData);

    expect(result.nodes).toBeDefined();
    expect(result.edges).toBeDefined();
    expect(result.nodes).toHaveLength(2);
    expect(result.edges).toHaveLength(1);
  });

  it("invalid input (origem references non-existent lancamento) → throws", () => {
    const chainData: ChainData = {
      documentos: [
        {
          id: "1",
          numero: "M1",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-01",
        },
      ],
      lancamentos: [],
      origens: [{ id: "orig-1", lancamentoId: "nonexistent", documentoId: "1" }],
    };

    expect(() => buildGraph(chainData)).toThrow(
      /Origem orig-1 references non-existent lancamento: nonexistent/
    );
  });

  it("invalid input (origem references non-existent documento) → throws", () => {
    const chainData: ChainData = {
      documentos: [
        {
          id: "1",
          numero: "M1",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-01",
        },
      ],
      lancamentos: [
        { id: "lanc-1", documentoId: "1", tipo: "registro" as LancamentoTipo },
      ],
      origens: [
        { id: "orig-1", lancamentoId: "lanc-1", documentoId: "nonexistent" }
      ],
    };

    expect(() => buildGraph(chainData)).toThrow(
      /Origem orig-1 references non-existent documento: nonexistent/
    );
  });

  it("NICE #1: ChainData with lancamento referenced by origem but missing documento → throws", () => {
    const chainData: ChainData = {
      documentos: [
        {
          id: "1",
          numero: "M1",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-01",
        },
      ],
      lancamentos: [
        {
          id: "lanc-1",
          documentoId: "nonexistent-doc",
          tipo: "registro" as LancamentoTipo,
        },
      ],
      origens: [{ id: "orig-1", lancamentoId: "lanc-1", documentoId: "1" }],
    };

    expect(() => buildGraph(chainData)).toThrow(
      /Lancamento lanc-1 references non-existent documento: nonexistent-doc/
    );
  });

  // --- Fim-cadeia classification (2 cases) ---

  it("explicit fim-cadeia origens render their tipo_fim_cadeia classification", () => {
    const chainData: ChainData = {
      documentos: [
        {
          id: "1",
          numero: "M1",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-01",
        },
      ],
      lancamentos: [
        { id: "lanc-1", documentoId: "1", tipo: "registro" as LancamentoTipo },
      ],
      origens: [
        {
          id: "orig-fim",
          lancamentoId: "lanc-1",
          documentoId: null,
          tipoOrigem: "fim_cadeia",
          tipoFimCadeia: "destacamento_publico",
          especificacao: "Terra pública",
        },
      ],
    };

    const result = buildGraph(chainData);
    const fimNodes = result.nodes.filter((n) => n.type === "fimCadeia");

    expect(fimNodes).toHaveLength(1);
    expect(fimNodes[0]?.data).toEqual({
      classificacao: "destacamento_publico",
      especificacao: "Terra pública",
    });
    expect(result.edges).toContainEqual({
      id: "orig-fim",
      source: "doc-1",
      target: "fim-orig-fim",
      data: { tipoOrigem: "fim_cadeia" },
    });
  });

  it("null-documento matricula origem renders as unresolved citation leaf", () => {
    const chainData: ChainData = {
      documentos: [
        {
          id: "1",
          numero: "M1",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-01",
        },
      ],
      lancamentos: [
        { id: "lanc-1", documentoId: "1", tipo: "registro" as LancamentoTipo },
      ],
      origens: [
        {
          id: "2854",
          lancamentoId: "lanc-1",
          documentoId: null,
          tipoOrigem: "matricula",
          numero: "46984",
        },
      ],
    };

    const result = buildGraph(chainData);

    expect(result.nodes).toContainEqual({
      id: "unresolved-2854",
      label: "Matrícula 46984",
      type: "fimCadeia",
      data: {
        label: "Matrícula 46984",
        classificacao: "nao_resolvida",
      },
    });
    expect(result.edges).toContainEqual({
      id: "2854",
      source: "doc-1",
      target: "unresolved-2854",
      data: { tipoOrigem: "matricula" },
    });
  });

  it("synthetic fim-cadeia nodes have classificacao: inconclusa", () => {
    const chainData: ChainData = {
      documentos: [
        {
          id: "1",
          numero: "M1",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-01",
        },
      ],
      lancamentos: [],
      origens: [],
    };

    const result = buildGraph(chainData);

    const fimNode = result.nodes.find((n) => n.type === "fimCadeia");
    expect(fimNode).toBeDefined();
    expect(fimNode?.data.classificacao).toBe("inconclusa");
  });

  // --- Cycle detection (2 cases) ---

  it("self-loop (documento with origem pointing to itself) → throws cycle error", () => {
    const chainData: ChainData = {
      documentos: [
        {
          id: "1",
          numero: "M1",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-01",
        },
      ],
      lancamentos: [
        { id: "lanc-1", documentoId: "1", tipo: "registro" as LancamentoTipo },
      ],
      origens: [
        { id: "orig-1", lancamentoId: "lanc-1", documentoId: "1" }, // Self-loop
      ],
    };

    expect(() => buildGraph(chainData)).toThrow(
      /Cycle detected in chain data: doc-1 -> doc-1/
    );
  });

  it("2-node cycle (doc-1 → doc-2 → doc-1) → throws cycle error", () => {
    const chainData: ChainData = {
      documentos: [
        {
          id: "1",
          numero: "M1",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-01",
        },
        {
          id: "2",
          numero: "M2",
          tipo: "matricula",
          cartorioId: "cartorio-1",
          data: "2024-01-02",
        },
      ],
      lancamentos: [
        { id: "lanc-1", documentoId: "2", tipo: "registro" as LancamentoTipo },
        { id: "lanc-2", documentoId: "1", tipo: "registro" as LancamentoTipo },
      ],
      origens: [
        { id: "orig-1", lancamentoId: "lanc-1", documentoId: "1" }, // 1 → 2
        { id: "orig-2", lancamentoId: "lanc-2", documentoId: "2" }, // 2 → 1 (cycle)
      ],
    };

    expect(() => buildGraph(chainData)).toThrow(
      /Cycle detected in chain data: (doc-1 -> doc-2 -> doc-1|doc-2 -> doc-1 -> doc-2)/
    );
  });
});
