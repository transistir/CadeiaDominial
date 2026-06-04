import { describe, it, expect } from "vitest";
import { validateGraph } from "./validateGraph";
import type { GraphJson } from "./types";

describe("validateGraph", () => {
  const validGraph: GraphJson = {
    nodes: [
      { id: "a", label: "Node A", type: "default" },
      { id: "b", label: "Node B", type: "default" },
    ],
    edges: [{ id: "a-b", source: "a", target: "b" }],
  };

  it("passes for valid graph", () => {
    expect(() => validateGraph(validGraph)).not.toThrow();
  });

  it("throws on duplicate node IDs", () => {
    const graph: GraphJson = {
      nodes: [
        { id: "a", label: "Node A", type: "default" },
        { id: "a", label: "Node A Duplicate", type: "default" },
      ],
      edges: [],
    };
    expect(() => validateGraph(graph)).toThrow(/Duplicate node ID: a/);
  });

  it("throws on duplicate edge IDs", () => {
    const graph: GraphJson = {
      nodes: [
        { id: "a", label: "Node A", type: "default" },
        { id: "b", label: "Node B", type: "default" },
      ],
      edges: [
        { id: "dup", source: "a", target: "b" },
        { id: "dup", source: "b", target: "a" },
      ],
    };
    expect(() => validateGraph(graph)).toThrow(/Duplicate edge ID: dup/);
  });

  it("throws on edge referencing non-existent source", () => {
    const graph: GraphJson = {
      nodes: [{ id: "b", label: "Node B", type: "default" }],
      edges: [{ id: "e1", source: "a", target: "b" }],
    };
    expect(() => validateGraph(graph)).toThrow(/Edge e1 references non-existent source: a/);
  });

  it("throws on edge referencing non-existent target", () => {
    const graph: GraphJson = {
      nodes: [{ id: "a", label: "Node A", type: "default" }],
      edges: [{ id: "e1", source: "a", target: "b" }],
    };
    expect(() => validateGraph(graph)).toThrow(/Edge e1 references non-existent target: b/);
  });
});
