import { describe, it, expect } from "vitest";
import {
  generateChainTopology,
  toGraphJson,
  assertTopologyInvariants,
  type TopologyGraph
} from "../chain-topology";

describe("chain-topology.branching", () => {
  it("n=3 branching produces 3 docs, 2 lancs, 2 fims", () => {
    const g = generateChainTopology(42, 3, { shape: "branching" });
    expect(g.documentos).toHaveLength(3);
    expect(g.lancamentos).toHaveLength(2);
    expect(g.origens).toHaveLength(2);
    expect(g.fimCadeias).toHaveLength(2);
    assertTopologyInvariants(g);
  });

  it("n=6 branching produces 6 docs, 5 lancs, 2 fims", () => {
    const g = generateChainTopology(42, 6, { shape: "branching" });
    expect(g.documentos).toHaveLength(6);
    expect(g.lancamentos).toHaveLength(5);
    expect(g.origens).toHaveLength(5);
    expect(g.fimCadeias).toHaveLength(2);
    assertTopologyInvariants(g);
  });

  it("branching has exactly one node with 2 outgoing edges (the branch point)", () => {
    const g = generateChainTopology(42, 6, { shape: "branching" });
    const outgoing = new Map<string, number>();
    for (const d of g.documentos) outgoing.set(d.id, 0);
    for (const l of g.lancamentos) {
      const sourceDoc = g.origens.find((o) => o.lancamentoId === l.id)!.documentoId;
      outgoing.set(sourceDoc, (outgoing.get(sourceDoc) ?? 0) + 1);
    }
    const twoOut = [...outgoing.entries()].filter(([, n]) => n === 2);
    expect(twoOut).toHaveLength(1);
    expect(twoOut[0]![0]).toBe("doc-4");
  });

  it("branching n=3 branch point is doc-1", () => {
    const g = generateChainTopology(42, 3, { shape: "branching" });
    const outgoing = new Map<string, number>();
    for (const d of g.documentos) outgoing.set(d.id, 0);
    for (const l of g.lancamentos) {
      const sourceDoc = g.origens.find((o) => o.lancamentoId === l.id)!.documentoId;
      outgoing.set(sourceDoc, (outgoing.get(sourceDoc) ?? 0) + 1);
    }
    const twoOut = [...outgoing.entries()].filter(([, n]) => n === 2);
    expect(twoOut).toHaveLength(1);
    expect(twoOut[0]![0]).toBe("doc-1");
  });

  it("branching terminal children are doc-(n-1) and doc-n", () => {
    const g = generateChainTopology(42, 6, { shape: "branching" });
    const terminalDocs = g.fimCadeias.map((f) => {
      const ori = g.origens.find((o) => o.id === f.origemId)!;
      const lanc = g.lancamentos.find((l) => l.id === ori.lancamentoId)!;
      return lanc.documentoId;
    });
    expect(terminalDocs.sort()).toEqual(["doc-5", "doc-6"]);
  });

  it("branching is deterministic for same seed", () => {
    const a: TopologyGraph = generateChainTopology(99, 7, {
      shape: "branching"
    });
    const b: TopologyGraph = generateChainTopology(99, 7, {
      shape: "branching"
    });
    expect(a).toEqual(b);
  });

  it("branching throws RangeError for n < 3", () => {
    expect(() => generateChainTopology(42, 1, { shape: "branching" })).toThrow(RangeError);
    expect(() => generateChainTopology(42, 2, { shape: "branching" })).toThrow(RangeError);
  });
});

describe("chain-topology.merge", () => {
  it("n=3 merge produces 3 docs, 1 lanc, 2 fims", () => {
    // Plan S-4: merge n=3 is the minimal merge — 1 Registro with 2
    // origens, no suffix. Both origens are terminal (their target
    // doc-3 has no outgoing origens) so 2 fims. Lancs = 1, not n-1
    // (the merge point consolidates 2 sources into 1 lanc).
    const g = generateChainTopology(42, 3, { shape: "merge" });
    expect(g.documentos).toHaveLength(3);
    expect(g.lancamentos).toHaveLength(1);
    expect(g.origens).toHaveLength(2);
    expect(g.fimCadeias).toHaveLength(2);
    assertTopologyInvariants(g);
  });

  it("n=6 merge produces 6 docs, 4 lancs, 1 fim", () => {
    // 1 merge lanc + (n-3) = 3 suffix lancs = 4 lancs total. The
    // suffix flows from doc-3, so ori-1, ori-2 (merge point sources)
    // and the first two suffix origens are non-terminal; only the
    // last suffix origem is terminal → 1 fim.
    const g = generateChainTopology(42, 6, { shape: "merge" });
    expect(g.documentos).toHaveLength(6);
    expect(g.lancamentos).toHaveLength(4);
    expect(g.origens).toHaveLength(5);
    expect(g.fimCadeias).toHaveLength(1);
    assertTopologyInvariants(g);
  });

  it("merge has exactly one node with 2 incoming origens (the merge point)", () => {
    // A merge is 2 origens pointing at 1 lancamento, not 2 lancs. So
    // the merge point doc-3 has 1 incoming lanc but 2 incoming origens.
    // We test the origem property because that is what makes a merge
    // a merge (vs a regular suffix).
    const g = generateChainTopology(42, 6, { shape: "merge" });
    const incomingOrigens = new Map<string, number>();
    for (const d of g.documentos) incomingOrigens.set(d.id, 0);
    for (const o of g.origens) {
      // An origem targets a doc indirectly via its lancamento. Find
      // the lanc's target documentoId and count it.
      const lanc = g.lancamentos.find((l) => l.id === o.lancamentoId)!;
      incomingOrigens.set(lanc.documentoId, (incomingOrigens.get(lanc.documentoId) ?? 0) + 1);
    }
    const twoIn = [...incomingOrigens.entries()].filter(([, n]) => n === 2);
    expect(twoIn).toHaveLength(1);
    expect(twoIn[0]![0]).toBe("doc-3");
  });

  it("merge n=6 has a 2-origem merge point at doc-3 (not testable at n=3 since suffix differentiates it)", () => {
    // At n=3, both merge origens are terminal and there's no suffix
    // flow, so the merge is structurally indistinguishable from a
    // 2-origem leaf cluster by the "incoming origens" metric alone.
    // But the count of incoming origens at doc-3 is still 2.
    const g = generateChainTopology(42, 6, { shape: "merge" });
    const incomingOrigens = new Map<string, number>();
    for (const d of g.documentos) incomingOrigens.set(d.id, 0);
    for (const o of g.origens) {
      const lanc = g.lancamentos.find((l) => l.id === o.lancamentoId)!;
      incomingOrigens.set(lanc.documentoId, (incomingOrigens.get(lanc.documentoId) ?? 0) + 1);
    }
    expect(incomingOrigens.get("doc-3")).toBe(2);
  });

  it("merge terminal document is doc-n", () => {
    const n = 6;
    const g = generateChainTopology(42, n, { shape: "merge" });
    expect(g.fimCadeias).toHaveLength(1);
    const ori = g.origens.find((o) => o.id === g.fimCadeias[0]!.origemId)!;
    const sourceLanc = g.lancamentos.find((l) => l.id === ori.lancamentoId)!;
    expect(sourceLanc.documentoId).toBe(`doc-${n}`);
  });

  it("merge sources doc-1 and doc-2 have no incoming edges", () => {
    const g = generateChainTopology(42, 6, { shape: "merge" });
    const incoming = new Map<string, number>();
    for (const d of g.documentos) incoming.set(d.id, 0);
    for (const l of g.lancamentos) {
      incoming.set(l.documentoId, (incoming.get(l.documentoId) ?? 0) + 1);
    }
    expect(incoming.get("doc-1")).toBe(0);
    expect(incoming.get("doc-2")).toBe(0);
  });

  it("merge is deterministic for same seed", () => {
    const a: TopologyGraph = generateChainTopology(99, 7, { shape: "merge" });
    const b: TopologyGraph = generateChainTopology(99, 7, { shape: "merge" });
    expect(a).toEqual(b);
  });

  it("merge throws RangeError for n < 3", () => {
    expect(() => generateChainTopology(42, 1, { shape: "merge" })).toThrow(RangeError);
    expect(() => generateChainTopology(42, 2, { shape: "merge" })).toThrow(RangeError);
  });
});

describe("chain-topology.shapes differ", () => {
  it("branching and merge produce structurally different graphs at n=3", () => {
    const b = generateChainTopology(1, 3, { shape: "branching" });
    const m = generateChainTopology(1, 3, { shape: "merge" });
    // Branching at n=3: 2 branch lancs out of doc-1. The branch point
    // is a doc with 2 outgoing lancs.
    // Merge at n=3: 1 merge lanc with 2 incoming origens at doc-3.
    // The branch point is a doc with 2 outgoing lancs; the merge
    // point is a doc with 2 incoming origens. They are NOT the same.
    const bOutgoing = new Map<string, number>();
    for (const d of b.documentos) bOutgoing.set(d.id, 0);
    for (const l of b.lancamentos) {
      const sourceDoc = b.origens.find((o) => o.lancamentoId === l.id)!.documentoId;
      bOutgoing.set(sourceDoc, (bOutgoing.get(sourceDoc) ?? 0) + 1);
    }
    const mIncomingOrigens = new Map<string, number>();
    for (const d of m.documentos) mIncomingOrigens.set(d.id, 0);
    for (const o of m.origens) {
      const lanc = m.lancamentos.find((l) => l.id === o.lancamentoId)!;
      mIncomingOrigens.set(lanc.documentoId, (mIncomingOrigens.get(lanc.documentoId) ?? 0) + 1);
    }
    // Branch has 1 doc with 2 outgoing lancs; merge has 0 such docs.
    expect([...bOutgoing.values()].filter((n) => n === 2)).toHaveLength(1);
    // Merge has 1 doc with 2 incoming origens; branch has 0 such docs.
    expect([...mIncomingOrigens.values()].filter((n) => n === 2)).toHaveLength(1);
  });
});

describe("chain-topology.toGraphJson for branching/merge", () => {
  it("branching n=6 GraphJson has valid node/edge structure", () => {
    const g = generateChainTopology(42, 6, { shape: "branching" });
    const json = toGraphJson(g);
    const nodeIds = new Set(json.nodes.map((n) => n.id));
    for (const edge of json.edges) {
      expect(nodeIds.has(edge.source)).toBe(true);
      expect(nodeIds.has(edge.target)).toBe(true);
    }
  });

  it("merge n=6 GraphJson has valid node/edge structure", () => {
    const g = generateChainTopology(42, 6, { shape: "merge" });
    const json = toGraphJson(g);
    const nodeIds = new Set(json.nodes.map((n) => n.id));
    for (const edge of json.edges) {
      expect(nodeIds.has(edge.source)).toBe(true);
      expect(nodeIds.has(edge.target)).toBe(true);
    }
  });
});
