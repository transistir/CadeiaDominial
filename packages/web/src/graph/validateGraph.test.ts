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

  it("returns a strongly-typed GraphJson for valid input", () => {
    const result = validateGraph(validGraph);
    expect(result.nodes).toHaveLength(2);
    expect(result.edges).toHaveLength(1);
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
        { id: "a", label: "A", type: "default" },
        { id: 123, label: "B", type: "default" }, // id is not a string
      ],
      edges: [],
    };
    expect(() => validateGraph(bad)).toThrow(/nodes\[1\]\.id must be a non-empty string/);
  });

  it("throws when an edge is missing required string fields", () => {
    const bad: unknown = {
      nodes: [{ id: "a", label: "A", type: "default" }],
      edges: [{ id: "e1", source: "a" }], // target missing
    };
    expect(() => validateGraph(bad)).toThrow(/edges\[0\]\.target must be a non-empty string/);
  });

  it("accepts arbitrary JSON-shaped unknown input that is structurally valid", () => {
    const json = JSON.parse(
      '{"nodes":[{"id":"x","label":"X","type":"t"}],"edges":[]}'
    );
    const result = validateGraph(json);
    expect(result.nodes[0].id).toBe("x");
  });
});
