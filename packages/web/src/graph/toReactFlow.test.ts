import { describe, it, expect } from "vitest";
import { toReactFlow } from "./toReactFlow";
import type { LayoutedGraph } from "./layoutGraph";

describe("toReactFlow", () => {
  const layouted: LayoutedGraph = {
    nodes: [
      {
        id: "doc-a",
        label: "Node A",
        type: "documento",
        position: { x: 0, y: 0 },
        data: { numero: "M123", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-15" }
      },
      {
        id: "fim-b",
        label: "Node B",
        type: "fimCadeia",
        position: { x: 200, y: 0 },
        data: { classificacao: "inconclusa" }
      }
    ],
    edges: [
      { id: "doc-a-fim-b", source: "doc-a", target: "fim-b", data: { tipoOrigem: "matricula" } },
      { id: "fallback", source: "fim-b", target: "doc-a" }
    ]
  };

  it("converts nodes to React Flow format", () => {
    const result = toReactFlow(layouted);
    expect(result.nodes).toHaveLength(2);
    const nodeA = result.nodes.find((n) => n.id === "doc-a");
    expect(nodeA?.type).toBe("documento");
    expect(nodeA?.position).toEqual({ x: 0, y: 0 });
    expect(nodeA?.data).toEqual(layouted.nodes[0].data);
    expect(nodeA?.draggable).toBe(false);

    const nodeB = result.nodes.find((n) => n.id === "fim-b");
    expect(nodeB?.type).toBe("fimCadeia");
    expect(nodeB?.data).toEqual(layouted.nodes[1].data);
  });

  it("converts edges to React Flow format", () => {
    const result = toReactFlow(layouted);
    expect(result.edges).toHaveLength(2);
    const edge = result.edges[0];
    expect(edge.id).toBe("doc-a-fim-b");
    expect(edge.source).toBe("doc-a");
    expect(edge.target).toBe("fim-b");
    expect(edge.type).toBe("origem");
    expect(edge.animated).toBe(false);
    expect(edge.data).toEqual(layouted.edges[0].data);
  });

  it("keeps smoothstep for edges without tipoOrigem", () => {
    const result = toReactFlow(layouted);
    const edge = result.edges.find((e) => e.id === "fallback");
    expect(edge?.type).toBe("smoothstep");
    expect(edge?.data).toBeUndefined();
  });

  it("preserves all nodes and edges", () => {
    const result = toReactFlow(layouted);
    expect(result.nodes.length).toBe(layouted.nodes.length);
    expect(result.edges.length).toBe(layouted.edges.length);
  });

  it("falls back to label data when layout data is missing", () => {
    const result = toReactFlow({
      nodes: [
        { id: "doc-missing-data", label: "Fallback", type: "documento", position: { x: 0, y: 0 } }
      ],
      edges: []
    });

    expect(result.nodes[0].data).toEqual({ label: "Fallback" });
  });
});
