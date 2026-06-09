import { describe, it, expect } from "vitest";
import { validateGraph } from "./validateGraph";
import type { GraphJson } from "./types";
import basicGraphFixture from "./fixtures/basic-graph.json";

describe("validateGraph", () => {
  const validGraph: GraphJson = {
    nodes: [
      {
        id: "doc-a",
        label: "Node A",
        type: "documento",
        data: { numero: "M123", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-15" }
      },
      {
        id: "doc-b",
        label: "Node B",
        type: "documento",
        data: { numero: "T456", tipo: "transcricao", cartorioId: "cartorio-2", data: "2024-01-16" }
      }
    ],
    edges: [{ id: "lanc-a-b", source: "doc-a", target: "doc-b" }]
  };

  it("passes for valid graph", () => {
    expect(() => validateGraph(validGraph)).not.toThrow();
  });

  it("returns a strongly-typed GraphJson for valid input", () => {
    const result = validateGraph(validGraph);
    expect(result.nodes).toHaveLength(2);
    expect(result.edges).toHaveLength(1);
  });

  it("throws on duplicate node IDs", () => {
    const graph: GraphJson = {
      nodes: [
        {
          id: "doc-a",
          label: "Node A",
          type: "documento",
          data: { numero: "M123", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-15" }
        },
        {
          id: "doc-a",
          label: "Node A Duplicate",
          type: "documento",
          data: { numero: "M124", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-16" }
        }
      ],
      edges: []
    };
    expect(() => validateGraph(graph)).toThrow(/Duplicate node ID: doc-a/);
  });

  it("throws on duplicate edge IDs", () => {
    const graph: GraphJson = {
      nodes: [
        {
          id: "doc-a",
          label: "Node A",
          type: "documento",
          data: { numero: "M123", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-15" }
        },
        {
          id: "doc-b",
          label: "Node B",
          type: "documento",
          data: {
            numero: "T456",
            tipo: "transcricao",
            cartorioId: "cartorio-2",
            data: "2024-01-16"
          }
        }
      ],
      edges: [
        { id: "lanc-dup", source: "doc-a", target: "doc-b" },
        { id: "lanc-dup", source: "doc-b", target: "doc-a" }
      ]
    };
    expect(() => validateGraph(graph)).toThrow(/Duplicate edge ID: lanc-dup/);
  });

  it("throws on edge referencing non-existent source", () => {
    const graph: GraphJson = {
      nodes: [
        {
          id: "doc-b",
          label: "Node B",
          type: "documento",
          data: {
            numero: "T456",
            tipo: "transcricao",
            cartorioId: "cartorio-2",
            data: "2024-01-16"
          }
        }
      ],
      edges: [{ id: "lanc-1", source: "doc-a", target: "doc-b" }]
    };
    expect(() => validateGraph(graph)).toThrow(/Edge lanc-1 references non-existent source: doc-a/);
  });

  it("throws on edge referencing non-existent target", () => {
    const graph: GraphJson = {
      nodes: [
        {
          id: "doc-a",
          label: "Node A",
          type: "documento",
          data: { numero: "M123", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-15" }
        }
      ],
      edges: [{ id: "lanc-1", source: "doc-a", target: "doc-b" }]
    };
    expect(() => validateGraph(graph)).toThrow(/Edge lanc-1 references non-existent target: doc-b/);
  });

  // --- shape validation (N-3 fix) ---

  it("throws on null payload", () => {
    expect(() => validateGraph(null)).toThrow(/must be an object/);
  });

  it("throws on non-object payload", () => {
    expect(() => validateGraph("nope")).toThrow(/must be an object/);
    expect(() => validateGraph(42)).toThrow(/must be an object/);
    expect(() => validateGraph(true)).toThrow(/must be an object/);
  });

  it("throws when nodes is missing or not an array", () => {
    expect(() => validateGraph({ edges: [] })).toThrow(/Graph\.nodes must be an array/);
    expect(() => validateGraph({ nodes: "x", edges: [] })).toThrow(/Graph\.nodes must be an array/);
  });

  it("throws when edges is missing or not an array", () => {
    expect(() => validateGraph({ nodes: [] })).toThrow(/Graph\.edges must be an array/);
    expect(() => validateGraph({ nodes: [], edges: "x" })).toThrow(/Graph\.edges must be an array/);
  });

  it("throws when a node is missing required string fields", () => {
    const bad: unknown = {
      nodes: [
        {
          id: "doc-a",
          label: "A",
          type: "documento",
          data: { numero: "M123", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-15" }
        },
        { id: 123, label: "B", type: "documento" } // id is not a string
      ],
      edges: []
    };
    expect(() => validateGraph(bad)).toThrow(/nodes\[1\]\.id must be a non-empty string/);
  });

  it("throws when an edge is missing required string fields", () => {
    const bad: unknown = {
      nodes: [
        {
          id: "doc-a",
          label: "A",
          type: "documento",
          data: { numero: "M123", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-15" }
        }
      ],
      edges: [{ id: "lanc-1", source: "doc-a" }] // target missing
    };
    expect(() => validateGraph(bad)).toThrow(/edges\[0\]\.target must be a non-empty string/);
  });

  it("accepts arbitrary JSON-shaped unknown input that is structurally valid", () => {
    const json = JSON.parse(
      '{"nodes":[{"id":"doc-x","label":"X","type":"documento","data":{"numero":"M1","tipo":"matricula","cartorioId":"cartorio-1","data":"2024-01-15"}}],"edges":[]}'
    );
    const result = validateGraph(json);
    expect(result.nodes[0].id).toBe("doc-x");
  });

  it("rejects the committed basic-graph fixture until Item 5 updates it", () => {
    expect(() => validateGraph(basicGraphFixture)).toThrow(
      /nodes\[0\]\.type: invalid value 'source'/
    );
  });

  it("accepts a documento node with all required fields", () => {
    const graph: GraphJson = {
      nodes: [
        {
          id: "doc-1",
          label: "M123",
          type: "documento",
          data: { numero: "M123", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-15" }
        }
      ],
      edges: []
    };

    const result = validateGraph(graph);
    expect(result.nodes[0]).toEqual(graph.nodes[0]);
  });

  it("accepts a fimCadeia node with classificacao", () => {
    const graph: GraphJson = {
      nodes: [
        {
          id: "fim-1",
          label: "Fim de cadeia",
          type: "fimCadeia",
          data: { classificacao: "origem_lidima" }
        }
      ],
      edges: []
    };

    const result = validateGraph(graph);
    expect(result.nodes[0]).toEqual(graph.nodes[0]);
  });

  it("accepts an edge with optional data.tipoOrigem", () => {
    const graph: GraphJson = {
      nodes: [
        {
          id: "doc-1",
          label: "M123",
          type: "documento",
          data: { numero: "M123", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-15" }
        },
        {
          id: "fim-1",
          label: "Fim de cadeia",
          type: "fimCadeia",
          data: { classificacao: "inconclusa" }
        }
      ],
      edges: [
        { id: "lanc-1", source: "doc-1", target: "fim-1", data: { tipoOrigem: "fim_cadeia" } }
      ]
    };

    const result = validateGraph(graph);
    expect(result.edges[0]).toEqual(graph.edges[0]);
  });

  it("rejects a node with an invalid type", () => {
    const graph: unknown = {
      nodes: [{ id: "doc-1", label: "Old source", type: "source", data: {} }],
      edges: []
    };

    expect(() => validateGraph(graph)).toThrow(/nodes\[0\]\.type: invalid value 'source'/);
  });

  it("rejects a documento missing data.tipo", () => {
    const graph: unknown = {
      nodes: [
        {
          id: "doc-1",
          label: "M123",
          type: "documento",
          data: { numero: "M123", cartorioId: "cartorio-1", data: "2024-01-15" }
        }
      ],
      edges: []
    };

    expect(() => validateGraph(graph)).toThrow(/nodes\[0\]\.data\.tipo: invalid value undefined/);
  });

  it("rejects a documento with invalid tipo", () => {
    const graph: unknown = {
      nodes: [
        {
          id: "doc-1",
          label: "M123",
          type: "documento",
          data: { numero: "M123", tipo: "foo", cartorioId: "cartorio-1", data: "2024-01-15" }
        }
      ],
      edges: []
    };

    expect(() => validateGraph(graph)).toThrow(/nodes\[0\]\.data\.tipo: invalid value 'foo'/);
  });

  it("rejects a fimCadeia with invalid classificacao", () => {
    const graph: unknown = {
      nodes: [
        {
          id: "fim-1",
          label: "Fim de cadeia",
          type: "fimCadeia",
          data: { classificacao: "bar" }
        }
      ],
      edges: []
    };

    expect(() => validateGraph(graph)).toThrow(
      /nodes\[0\]\.data\.classificacao: invalid value 'bar'/
    );
  });

  it("rejects an edge with invalid data.tipoOrigem", () => {
    const graph: unknown = {
      nodes: [
        {
          id: "doc-1",
          label: "M123",
          type: "documento",
          data: { numero: "M123", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-15" }
        },
        {
          id: "fim-1",
          label: "Fim de cadeia",
          type: "fimCadeia",
          data: { classificacao: "sem_origem" }
        }
      ],
      edges: [{ id: "lanc-1", source: "doc-1", target: "fim-1", data: { tipoOrigem: "invalid" } }]
    };

    expect(() => validateGraph(graph)).toThrow(
      /edges\[0\]\.data\.tipoOrigem: invalid value 'invalid'/
    );
  });

  it("rejects a node id without the proper prefix", () => {
    const graph: unknown = {
      nodes: [
        {
          id: "node-1",
          label: "M123",
          type: "documento",
          data: { numero: "M123", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-15" }
        }
      ],
      edges: []
    };

    expect(() => validateGraph(graph)).toThrow(
      /nodes\[0\]\.id: expected prefix 'doc-', got 'node-1'/
    );
  });

  it("rejects duplicate node ids across types", () => {
    const graph: unknown = {
      nodes: [
        {
          id: "doc-1",
          label: "M123",
          type: "documento",
          data: { numero: "M123", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-15" }
        },
        {
          id: "doc-1",
          label: "Fim de cadeia",
          type: "fimCadeia",
          data: { classificacao: "inconclusa" }
        }
      ],
      edges: []
    };

    expect(() => validateGraph(graph)).toThrow(/Duplicate node ID: doc-1/);
  });
});
