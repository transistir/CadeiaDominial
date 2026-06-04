import { describe, it, expect } from "vitest";
import { layoutGraph } from "./layoutGraph";
import type { GraphJson } from "./types";

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
});
