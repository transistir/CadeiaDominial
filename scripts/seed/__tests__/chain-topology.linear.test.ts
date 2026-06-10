import { describe, it, expect } from "vitest";
import { generateChainTopology, toGraphJson, type TopologyGraph } from "../chain-topology";

describe("chain-topology.linear", () => {
  it("3-document linear produces 3 docs, 2 lancamentos, 1 fim", () => {
    const g = generateChainTopology(42, 3, { shape: "linear" });
    expect(g.documentos).toHaveLength(3);
    expect(g.lancamentos).toHaveLength(2);
    expect(g.origens).toHaveLength(2);
    expect(g.fimCadeias).toHaveLength(1);
  });

  it("1-document linear produces 1 doc, 0 lancamentos, 0 fims", () => {
    const g = generateChainTopology(42, 1, { shape: "linear" });
    expect(g.documentos).toHaveLength(1);
    expect(g.lancamentos).toHaveLength(0);
    expect(g.origens).toHaveLength(0);
    expect(g.fimCadeias).toHaveLength(0);
  });

  it("2-document linear produces 2 docs, 1 lancamento, 1 fim", () => {
    const g = generateChainTopology(42, 2, { shape: "linear" });
    expect(g.documentos).toHaveLength(2);
    expect(g.lancamentos).toHaveLength(1);
    expect(g.origens).toHaveLength(1);
    expect(g.fimCadeias).toHaveLength(1);
  });

  it("n-document linear has n-1 lancamentos and n-1 origens", () => {
    for (const n of [1, 2, 3, 4, 5, 10]) {
      const g = generateChainTopology(7, n, { shape: "linear" });
      expect(g.documentos).toHaveLength(n);
      expect(g.lancamentos).toHaveLength(n - 1);
      expect(g.origens).toHaveLength(n - 1);
    }
  });

  it("document IDs follow the doc-${i} pattern", () => {
    const g = generateChainTopology(42, 5, { shape: "linear" });
    expect(g.documentos.map((d) => d.id)).toEqual(["doc-1", "doc-2", "doc-3", "doc-4", "doc-5"]);
  });

  it("lancamento IDs follow the lanc-${i} pattern", () => {
    const g = generateChainTopology(42, 5, { shape: "linear" });
    expect(g.lancamentos.map((l) => l.id)).toEqual(["lanc-1", "lanc-2", "lanc-3", "lanc-4"]);
  });

  it("origem IDs follow the ori-${i} pattern", () => {
    const g = generateChainTopology(42, 4, { shape: "linear" });
    expect(g.origens.map((o) => o.id)).toEqual(["ori-1", "ori-2", "ori-3"]);
  });

  it("first lancamento creates doc-2 and originates from doc-1", () => {
    const g = generateChainTopology(42, 3, { shape: "linear" });
    const l1 = g.lancamentos.find((l) => l.id === "lanc-1")!;
    const o1 = g.origens.find((o) => o.id === "ori-1")!;
    expect(l1.documentoId).toBe("doc-2");
    expect(o1.lancamentoId).toBe("lanc-1");
    expect(o1.documentoId).toBe("doc-1");
  });

  it("last lancamento creates doc-n and originates from doc-(n-1)", () => {
    const n = 4;
    const g = generateChainTopology(42, n, { shape: "linear" });
    const lastLanc = g.lancamentos.find((l) => l.id === `lanc-${n - 1}`)!;
    const lastOri = g.origens.find((o) => o.id === `ori-${n - 1}`)!;
    expect(lastLanc.documentoId).toBe(`doc-${n}`);
    expect(lastOri.lancamentoId).toBe(`lanc-${n - 1}`);
    expect(lastOri.documentoId).toBe(`doc-${n - 1}`);
  });

  it("the linear fim is attached to the last origem", () => {
    // The fim id format is implementation detail (counter-based via
    // computeTerminalFims); the contract is "exactly one fim, attached
    // to the last linear origem". We check the binding rather than
    // the id shape.
    const n = 4;
    const g = generateChainTopology(42, n, { shape: "linear" });
    expect(g.fimCadeias).toHaveLength(1);
    expect(g.fimCadeias[0]!.origemId).toBe(`ori-${n - 1}`);
  });

  it("documentoTipo is one of the fixed list", () => {
    const g = generateChainTopology(42, 10, { shape: "linear" });
    const valid = ["matricula", "transcricao"];
    for (const d of g.documentos) {
      expect(valid).toContain(d.tipo);
    }
  });

  it("same seed produces deep-equal output", () => {
    const a: TopologyGraph = generateChainTopology(12345, 5, {
      shape: "linear"
    });
    const b: TopologyGraph = generateChainTopology(12345, 5, {
      shape: "linear"
    });
    expect(a).toEqual(b);
  });

  it("different seeds can produce different tipo selections", () => {
    const a = generateChainTopology(1, 10, { shape: "linear" });
    const b = generateChainTopology(2, 10, { shape: "linear" });
    const aTipos = a.documentos.map((d) => d.tipo);
    const bTipos = b.documentos.map((d) => d.tipo);
    expect(aTipos).not.toEqual(bTipos);
  });

  it("toGraphJson produces structurally valid node/edge JSON", () => {
    const g = generateChainTopology(42, 3, { shape: "linear" });
    const json = toGraphJson(g);
    expect(json.nodes).toHaveLength(3 + 1);
    expect(json.edges).toHaveLength(2 + 1);
    for (const node of json.nodes) {
      expect(node.id).toBeTruthy();
      expect(typeof node.label).toBe("string");
      expect(typeof node.type).toBe("string");
      expect(node.data).toBeDefined();
    }
    for (const edge of json.edges) {
      expect(edge.id).toBeTruthy();
      expect(edge.source).toBeTruthy();
      expect(edge.target).toBeTruthy();
    }
  });

  it("toGraphJson edges reference real node IDs", () => {
    const g = generateChainTopology(42, 3, { shape: "linear" });
    const json = toGraphJson(g);
    const nodeIds = new Set(json.nodes.map((n) => n.id));
    for (const edge of json.edges) {
      expect(nodeIds.has(edge.source)).toBe(true);
      expect(nodeIds.has(edge.target)).toBe(true);
    }
  });
});
