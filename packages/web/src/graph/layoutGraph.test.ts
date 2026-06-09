import { describe, it, expect } from "vitest";
import { layoutGraph } from "./layoutGraph";
import { validateGraph } from "./validateGraph";
import type { GraphJson } from "./types";

// Frozen copies so the canonical fixture can't be mutated by tests.
import basicGraphFixture from "./fixtures/basic-graph.json";

const basicGraph: GraphJson = validateGraph(basicGraphFixture);

describe("layoutGraph", () => {
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
        data: { numero: "T456", tipo: "transcricao", cartorioId: "cartorio-2", data: "2024-01-16" }
      },
      {
        id: "fim-c",
        label: "Node C",
        type: "fimCadeia",
        data: { classificacao: "inconclusa" }
      }
    ],
    edges: [
      { id: "lanc-a-b", source: "doc-a", target: "doc-b" },
      { id: "lanc-b-c", source: "doc-b", target: "fim-c" }
    ]
  };

  it("returns all nodes with positions", () => {
    const result = layoutGraph(graph);
    expect(result.nodes).toHaveLength(3);
    result.nodes.forEach((node) => {
      expect(node.position).toBeDefined();
      expect(typeof node.position.x).toBe("number");
      expect(typeof node.position.y).toBe("number");
    });
  });

  it("preserves node properties", () => {
    const result = layoutGraph(graph);
    const nodeA = result.nodes.find((n) => n.id === "doc-a");
    expect(nodeA?.label).toBe("Node A");
    expect(nodeA?.type).toBe("documento");
    expect(nodeA?.data).toEqual(graph.nodes[0].data);
  });

  it("preserves edges", () => {
    const result = layoutGraph(graph);
    expect(result.edges).toHaveLength(2);
    expect(result.edges[0]).toEqual(graph.edges[0]);
  });

  it("produces deterministic layout for same input", () => {
    const result1 = layoutGraph(graph);
    const result2 = layoutGraph(graph);
    expect(result1.nodes).toEqual(result2.nodes);
  });

  it("layouts nodes in left-to-right direction", () => {
    const result = layoutGraph(graph);
    const nodeA = result.nodes.find((n) => n.id === "doc-a");
    const nodeB = result.nodes.find((n) => n.id === "doc-b");
    const nodeC = result.nodes.find((n) => n.id === "fim-c");
    // LR layout: a.x < b.x < c.x
    expect(nodeB!.position.x).toBeGreaterThan(nodeA!.position.x);
    expect(nodeC!.position.x).toBeGreaterThan(nodeB!.position.x);
  });

  // Golden test for the canonical fixture. The expected positions lock down
  // the deterministic LR layout so any unintended shift (dagre version bump,
  // constant change) is caught here, not by silent visual drift in the
  // committed screenshot.
  it("golden positions for canonical basic-graph fixture", () => {
    const result = layoutGraph(basicGraph);

    // Sanity: all 3 nodes + 2 edges from the fixture are present.
    expect(result.nodes).toHaveLength(3);
    expect(result.edges).toHaveLength(2);

    // M1234 is leftmost, Fim de cadeia is rightmost.
    const matricula = result.nodes.find((n) => n.label === "M1234")!;
    const transcricao = result.nodes.find((n) => n.label === "T5678")!;
    const fim = result.nodes.find((n) => n.label === "Fim de cadeia")!;
    expect(matricula.position.x).toBeLessThan(transcricao.position.x);
    expect(transcricao.position.x).toBeLessThan(fim.position.x);

    // All three nodes share the same y-coordinate (single rank, LR layout).
    expect(transcricao.position.y).toBeCloseTo(matricula.position.y, 5);
    expect(fim.position.y).toBeCloseTo(matricula.position.y, 5);

    // Exact x-positions are deterministic — locked down to catch layout shifts.
    // (ranksep=80, node width=180, so each subsequent node is 260 to the right.)
    expect(matricula.position.x).toBeCloseTo(0, 5);
    expect(transcricao.position.x).toBeCloseTo(260, 5);
    expect(fim.position.x).toBeCloseTo(520, 5);
  });
});
