import { describe, it, expect } from "vitest";
import { generateChainTopology, topologyToGraphJson } from "./topology-adapter";
import { validateGraph } from "./validateGraph";
import { layoutGraph } from "./layoutGraph";

describe("topology-adapter", () => {
  it("topologyToGraphJson for linear n=3 passes validateGraph", () => {
    const top = generateChainTopology(42, 3, { shape: "linear" });
    const json = topologyToGraphJson(top);
    const validated = validateGraph(json);
    expect(validated.nodes).toHaveLength(json.nodes.length);
    expect(validated.edges).toHaveLength(json.edges.length);
  });

  it("topologyToGraphJson for linear n=1 (1 doc, 0 edges) passes validateGraph", () => {
    const top = generateChainTopology(42, 1, { shape: "linear" });
    const json = topologyToGraphJson(top);
    expect(json.nodes).toHaveLength(1);
    expect(json.edges).toHaveLength(0);
    expect(() => validateGraph(json)).not.toThrow();
  });

  it("topologyToGraphJson for branching n=6 passes validateGraph", () => {
    const top = generateChainTopology(42, 6, { shape: "branching" });
    const json = topologyToGraphJson(top);
    expect(() => validateGraph(json)).not.toThrow();
  });

  it("topologyToGraphJson for merge n=6 passes validateGraph", () => {
    const top = generateChainTopology(42, 6, { shape: "merge" });
    const json = topologyToGraphJson(top);
    expect(() => validateGraph(json)).not.toThrow();
  });

  it("layoutGraph positions every node for all shapes", () => {
    for (const shape of ["linear", "branching", "merge"] as const) {
      const n = shape === "linear" ? 5 : 6;
      const top = generateChainTopology(42, n, { shape });
      const json = topologyToGraphJson(top);
      const validated = validateGraph(json);
      const layouted = layoutGraph(validated);
      expect(layouted.nodes).toHaveLength(validated.nodes.length);
      for (const node of layouted.nodes) {
        expect(typeof node.position.x).toBe("number");
        expect(typeof node.position.y).toBe("number");
      }
    }
  });

  it("re-exported generateChainTopology is callable from the web package", () => {
    expect(typeof generateChainTopology).toBe("function");
    const top = generateChainTopology(1, 3, { shape: "linear" });
    expect(top.documentos).toHaveLength(3);
  });

  it("all edge endpoints in the adapter output reference real node IDs", () => {
    const top = generateChainTopology(42, 4, { shape: "branching" });
    const json = topologyToGraphJson(top);
    const ids = new Set(json.nodes.map((n) => n.id));
    for (const edge of json.edges) {
      expect(ids.has(edge.source)).toBe(true);
      expect(ids.has(edge.target)).toBe(true);
    }
  });
});
