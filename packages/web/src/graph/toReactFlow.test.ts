import { describe, it, expect } from "vitest";
import { toReactFlow } from "./toReactFlow";
import type { LayoutedGraph } from "./layoutGraph";

describe("toReactFlow", () => {
  const layouted: LayoutedGraph = {
    nodes: [
      { id: "a", label: "Node A", type: "default", position: { x: 0, y: 0 } },
      { id: "b", label: "Node B", type: "default", position: { x: 200, y: 0 } },
    ],
    edges: [{ id: "a-b", source: "a", target: "b" }],
  };

  it("converts nodes to React Flow format", () => {
    const result = toReactFlow(layouted);
    expect(result.nodes).toHaveLength(2);
    const nodeA = result.nodes.find((n) => n.id === "a");
    expect(nodeA?.type).toBe("default");
    expect(nodeA?.position).toEqual({ x: 0, y: 0 });
    expect(nodeA?.data).toEqual({ label: "Node A" });
    expect(nodeA?.draggable).toBe(false);
  });

  it("converts edges to React Flow format", () => {
    const result = toReactFlow(layouted);
    expect(result.edges).toHaveLength(1);
    const edge = result.edges[0];
    expect(edge.id).toBe("a-b");
    expect(edge.source).toBe("a");
    expect(edge.target).toBe("b");
    expect(edge.type).toBe("smoothstep");
    expect(edge.animated).toBe(false);
  });

  it("preserves all nodes and edges", () => {
    const result = toReactFlow(layouted);
    expect(result.nodes.length).toBe(layouted.nodes.length);
    expect(result.edges.length).toBe(layouted.edges.length);
  });
});
