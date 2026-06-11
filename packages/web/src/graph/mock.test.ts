import { describe, it, expect } from "vitest";
import { generateMockGraph } from "./mock";
import { validateGraph } from "./validateGraph";

describe("generateMockGraph", () => {
  // --- Determinism (3 cases) ---

  it("linear shape → byte-identical output across calls", () => {
    const first = generateMockGraph("linear");
    const second = generateMockGraph("linear");

    expect(first).toEqual(second);
    expect(JSON.stringify(first)).toBe(JSON.stringify(second));
  });

  it("branching shape → byte-identical output across calls", () => {
    const first = generateMockGraph("branching");
    const second = generateMockGraph("branching");

    expect(first).toEqual(second);
    expect(JSON.stringify(first)).toBe(JSON.stringify(second));
  });

  it("merge shape → byte-identical output across calls", () => {
    const first = generateMockGraph("merge");
    const second = generateMockGraph("merge");

    expect(first).toEqual(second);
    expect(JSON.stringify(first)).toBe(JSON.stringify(second));
  });

  it("complex shape → byte-identical output across calls", () => {
    const first = generateMockGraph("complex");
    const second = generateMockGraph("complex");

    expect(first).toEqual(second);
    expect(JSON.stringify(first)).toBe(JSON.stringify(second));
  });

  // --- Shape verification (3 cases) ---

  it("linear shape → 6 nodes, 5 edges", () => {
    const graph = generateMockGraph("linear");

    expect(graph.nodes).toHaveLength(6);
    expect(graph.edges).toHaveLength(5);

    // 5 documento nodes + 1 synthetic fim
    const docNodes = graph.nodes.filter((n) => n.type === "documento");
    const fimNodes = graph.nodes.filter((n) => n.type === "fimCadeia");
    expect(docNodes).toHaveLength(5);
    expect(fimNodes).toHaveLength(1);

    // 4 doc→doc edges + 1 doc→fim edge
    const docToDocEdges = graph.edges.filter(
      (e) =>
        graph.nodes.find((n) => n.id === e.source)?.type === "documento" &&
        graph.nodes.find((n) => n.id === e.target)?.type === "documento"
    );
    const docToFimEdges = graph.edges.filter(
      (e) =>
        graph.nodes.find((n) => n.id === e.source)?.type === "documento" &&
        graph.nodes.find((n) => n.id === e.target)?.type === "fimCadeia"
    );
    expect(docToDocEdges).toHaveLength(4);
    expect(docToFimEdges).toHaveLength(1);
  });

  it("branching shape → 6 nodes, 5 edges", () => {
    const graph = generateMockGraph("branching");

    expect(graph.nodes).toHaveLength(6);
    expect(graph.edges).toHaveLength(5);

    // 4 documento nodes + 2 synthetic fims
    const docNodes = graph.nodes.filter((n) => n.type === "documento");
    const fimNodes = graph.nodes.filter((n) => n.type === "fimCadeia");
    expect(docNodes).toHaveLength(4);
    expect(fimNodes).toHaveLength(2);

    // 3 doc→doc edges + 2 doc→fim edges
    const docToDocEdges = graph.edges.filter(
      (e) =>
        graph.nodes.find((n) => n.id === e.source)?.type === "documento" &&
        graph.nodes.find((n) => n.id === e.target)?.type === "documento"
    );
    const docToFimEdges = graph.edges.filter(
      (e) =>
        graph.nodes.find((n) => n.id === e.source)?.type === "documento" &&
        graph.nodes.find((n) => n.id === e.target)?.type === "fimCadeia"
    );
    expect(docToDocEdges).toHaveLength(3);
    expect(docToFimEdges).toHaveLength(2);
  });

  it("merge shape → 4 nodes, 3 edges", () => {
    const graph = generateMockGraph("merge");

    expect(graph.nodes).toHaveLength(4);
    expect(graph.edges).toHaveLength(3);

    // 3 documento nodes + 1 synthetic fim
    const docNodes = graph.nodes.filter((n) => n.type === "documento");
    const fimNodes = graph.nodes.filter((n) => n.type === "fimCadeia");
    expect(docNodes).toHaveLength(3);
    expect(fimNodes).toHaveLength(1);

    // 2 doc→doc edges + 1 doc→fim edge
    const docToDocEdges = graph.edges.filter(
      (e) =>
        graph.nodes.find((n) => n.id === e.source)?.type === "documento" &&
        graph.nodes.find((n) => n.id === e.target)?.type === "documento"
    );
    const docToFimEdges = graph.edges.filter(
      (e) =>
        graph.nodes.find((n) => n.id === e.source)?.type === "documento" &&
        graph.nodes.find((n) => n.id === e.target)?.type === "fimCadeia"
    );
    expect(docToDocEdges).toHaveLength(2);
    expect(docToFimEdges).toHaveLength(1);
  });

  it("complex shape → 21 nodes, 20 edges", () => {
    const graph = generateMockGraph("complex");

    expect(graph.nodes).toHaveLength(21);
    expect(graph.edges).toHaveLength(20);

    // 16 documento nodes + 5 synthetic fims
    const docNodes = graph.nodes.filter((n) => n.type === "documento");
    const fimNodes = graph.nodes.filter((n) => n.type === "fimCadeia");
    expect(docNodes).toHaveLength(16);
    expect(fimNodes).toHaveLength(5);

    // 15 doc→doc edges + 5 doc→fim edges
    const docToDocEdges = graph.edges.filter(
      (e) =>
        graph.nodes.find((n) => n.id === e.source)?.type === "documento" &&
        graph.nodes.find((n) => n.id === e.target)?.type === "documento"
    );
    const docToFimEdges = graph.edges.filter(
      (e) =>
        graph.nodes.find((n) => n.id === e.source)?.type === "documento" &&
        graph.nodes.find((n) => n.id === e.target)?.type === "fimCadeia"
    );
    expect(docToDocEdges).toHaveLength(15);
    expect(docToFimEdges).toHaveLength(5);
  });

  // --- Node data completeness (1 case) ---

  it("all nodes have required data fields", () => {
    const linear = generateMockGraph("linear");
    const branching = generateMockGraph("branching");
    const merge = generateMockGraph("merge");
    const complex = generateMockGraph("complex");

    [linear, branching, merge, complex].forEach((graph) => {
      // Every documento node has numero, tipo, cartorioId, data
      const docNodes = graph.nodes.filter((n) => n.type === "documento");
      docNodes.forEach((node) => {
        if (node.type === "documento") {
          expect(node.data.numero).toBeDefined();
          expect(node.data.tipo).toBeDefined();
          expect(node.data.cartorioId).toBeDefined();
          expect(node.data.data).toBeDefined();
        }
      });

      // Every fimCadeia node has classificacao
      const fimNodes = graph.nodes.filter((n) => n.type === "fimCadeia");
      fimNodes.forEach((node) => {
        if (node.type === "fimCadeia") {
          expect(node.data.classificacao).toBeDefined();
        }
      });
    });
  });

  // --- Validation integration (1 case) ---

  it("output passes validateGraph() for all shapes", () => {
    const linear = generateMockGraph("linear");
    const branching = generateMockGraph("branching");
    const merge = generateMockGraph("merge");
    const complex = generateMockGraph("complex");

    expect(() => validateGraph(linear)).not.toThrow();
    expect(() => validateGraph(branching)).not.toThrow();
    expect(() => validateGraph(merge)).not.toThrow();
    expect(() => validateGraph(complex)).not.toThrow();
  });
});
