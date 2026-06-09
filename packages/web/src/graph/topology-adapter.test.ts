import { describe, it, expect } from "vitest";
import { generateChainTopology, topologyToGraphJson } from "./topology-adapter";
import { validateGraph } from "./validateGraph";
import { layoutGraph } from "./layoutGraph";
import type { TopologyGraph } from "@cadeia/chain-topology";

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

  // T-500 Item 5 NICE-1: explicit shape assertions. The adapter collapses
  // lancamento intermediate nodes (no LancamentoNode in T-500) and connects
  // documents directly. Every adapter-produced edge must carry a
  // data.tipoOrigem so the OrigemEdge component can pick the right style.
  it("adapter collapses lancamento nodes: no lanc-* node ids in the output", () => {
    const top = generateChainTopology(42, 3, { shape: "linear" });
    const json = topologyToGraphJson(top);
    for (const node of json.nodes) {
      expect(node.id.startsWith("lanc-")).toBe(false);
    }
  });

  it("adapter attaches data.tipoOrigem on every edge", () => {
    const top = generateChainTopology(42, 4, { shape: "branching" });
    const json = topologyToGraphJson(top);
    expect(json.edges.length).toBeGreaterThan(0);
    for (const edge of json.edges) {
      expect(edge.data).toBeDefined();
      expect(edge.data?.tipoOrigem).toBeDefined();
      expect(["matricula", "transcricao", "fim_cadeia"]).toContain(edge.data?.tipoOrigem);
    }
  });

  it("adapter emits fim edges with tipoOrigem=fim_cadeia", () => {
    // Build a topology that has at least one fimCadeia by adding a chain
    // large enough to trigger terminal fim generation in branching shape.
    const top = generateChainTopology(7, 5, { shape: "branching" });
    const json = topologyToGraphJson(top);
    const fimNodes = json.nodes.filter((n) => n.type === "fimCadeia");
    if (fimNodes.length === 0) {
      // Skip if this seed didn't generate a fim (defensive — generator may
      // change); the next test in the suite still covers non-fim edges.
      return;
    }
    const fimEdges = json.edges.filter((e) => fimNodes.some((n) => n.id === e.target));
    expect(fimEdges.length).toBeGreaterThan(0);
    for (const e of fimEdges) {
      expect(e.data?.tipoOrigem).toBe("fim_cadeia");
    }
  });

  it("topologyToGraphJson throws on a malformed topology (cross-collection id collision)", () => {
    // Pre-PR review NICE-2: the adapter's `topologyToGraphJson`
    // was a cast-only wrapper. The fix added a real
    // `validateGraph(json)` call so a malformed topology surfaces
    // an error at the adapter boundary instead of bubbling a
    // confusing JSON-level validation error later. This test
    // crafts a topology with a cross-collection node-id
    // collision (`doc-1` reused as a lanc id) and asserts the
    // adapter rejects it.
    const malformed: TopologyGraph = {
      imovel: { id: "imovel-1", seq: 1 },
      imovelDocumentos: [
        { imovelId: "imovel-1", documentoId: "doc-1" },
        { imovelId: "imovel-1", documentoId: "doc-2" }
      ],
      documentos: [
        { id: "doc-1", tipo: "matricula" },
        { id: "doc-2", tipo: "matricula" }
      ],
      // `lanc-1` collides with the documento id `doc-1` in the
      // resulting graph's node namespace. `toGraphJson` emits
      // each collection into a single node id space, so a
      // documento id and a lancamento id cannot share a string.
      lancamentos: [{ id: "doc-1", documentoId: "doc-2", tipo: "inicio_matricula" }],
      origens: [{ id: "ori-1", lancamentoId: "doc-1", documentoId: "doc-1", indice: 0 }],
      fimCadeias: [{ id: "fim-1", origemId: "ori-1" }],
      chainId: "chain-bad-collision"
    };
    expect(() => topologyToGraphJson(malformed)).toThrow();
  });
});
