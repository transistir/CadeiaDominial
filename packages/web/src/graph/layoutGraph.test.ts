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
      { id: "a", label: "Node A", type: "default" },
      { id: "b", label: "Node B", type: "default" },
      { id: "c", label: "Node C", type: "default" },
    ],
    edges: [
      { id: "a-b", source: "a", target: "b" },
      { id: "b-c", source: "b", target: "c" },
    ],
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
    const nodeA = result.nodes.find((n) => n.id === "a");
    expect(nodeA?.label).toBe("Node A");
    expect(nodeA?.type).toBe("default");
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
    const nodeA = result.nodes.find((n) => n.id === "a");
    const nodeB = result.nodes.find((n) => n.id === "b");
    const nodeC = result.nodes.find((n) => n.id === "c");
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

    // Field Data (source) is leftmost, Final Report (output) is rightmost.
    const field = result.nodes.find((n) => n.label === "Field Data")!;
    const analysis = result.nodes.find((n) => n.label === "Legal Analysis")!;
    const report = result.nodes.find((n) => n.label === "Final Report")!;
    expect(field.position.x).toBeLessThan(analysis.position.x);
    expect(analysis.position.x).toBeLessThan(report.position.x);

    // All three nodes share the same y-coordinate (single rank, LR layout).
    expect(analysis.position.y).toBeCloseTo(field.position.y, 5);
    expect(report.position.y).toBeCloseTo(field.position.y, 5);

    // Exact x-positions are deterministic — locked down to catch layout shifts.
    // (ranksep=80, node width=180, so each subsequent node is 260 to the right.)
    expect(field.position.x).toBeCloseTo(0, 5);
    expect(analysis.position.x).toBeCloseTo(260, 5);
    expect(report.position.x).toBeCloseTo(520, 5);
  });
});
