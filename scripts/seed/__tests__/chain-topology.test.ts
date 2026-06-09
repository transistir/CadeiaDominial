import { describe, it, expect } from "vitest";
import {
  generateChainTopology,
  toGraphJson,
  TopologyGraph,
} from "../chain-topology";

describe("chain-topology", () => {
  describe("exports topology contract", () => {
    it("should export generateChainTopology function", () => {
      expect(typeof generateChainTopology).toBe("function");
    });

    it("should accept seed, n, and options parameters", () => {
      expect(() => generateChainTopology(12345, 5, { shape: "linear" })).not.toThrow();
    });

    it("should return a TopologyGraph object", () => {
      const result = generateChainTopology(12345, 5);
      expect(result).toBeDefined();
      expect(result.documentos).toBeInstanceOf(Array);
      expect(result.lancamentos).toBeInstanceOf(Array);
      expect(result.origens).toBeInstanceOf(Array);
      expect(result.fimCadeias).toBeInstanceOf(Array);
      expect(typeof result.chainId).toBe("string");
    });

    it("should throw RangeError for n < 1", () => {
      expect(() => generateChainTopology(12345, 0)).toThrow(RangeError);
      expect(() => generateChainTopology(12345, -1)).toThrow(RangeError);
    });

    it("should throw RangeError for n = NaN, Infinity, or non-integer", () => {
      expect(() => generateChainTopology(12345, NaN)).toThrow(RangeError);
      expect(() => generateChainTopology(12345, Infinity)).toThrow(RangeError);
      expect(() => generateChainTopology(12345, -Infinity)).toThrow(RangeError);
      expect(() => generateChainTopology(12345, 2.5)).toThrow(RangeError);
      expect(() => generateChainTopology(12345, 1.0001)).toThrow(RangeError);
    });

    it("should reject non-integer n values (catches the NaN/Infinity hang bug)", () => {
      // Without Number.isSafeInteger, NaN < 1 is false (passes), and
      // the for loop "for (let i = 1; i <= NaN; i++)" simply never
      // executes, returning an empty graph. With Infinity, the loop
      // would hang trying to allocate 2^53 documents.
      expect(() => generateChainTopology(1, NaN)).toThrow(RangeError);
      expect(() => generateChainTopology(1, Infinity)).toThrow(RangeError);
    });

    it("should throw RangeError for branching with n < 3", () => {
      expect(() => generateChainTopology(12345, 2, { shape: "branching" })).toThrow(
        RangeError
      );
    });

    it("should throw RangeError for merge with n < 3", () => {
      expect(() => generateChainTopology(12345, 2, { shape: "merge" })).toThrow(
        RangeError
      );
    });

    it("should default to linear shape when not specified", () => {
      const result = generateChainTopology(12345, 5);
      expect(result).toBeDefined();
    });
  });

  describe("toGraphJson defensive guards", () => {
    it("skips fim edge when fim references a missing origem", () => {
      // Direct unit test of toGraphJson: a fim whose origemId is not in
      // the origens list triggers the `if (!ori) continue;` guard at
      // line 405. Generated topologies never do this, but the guard
      // exists for robustness.
      const graph: TopologyGraph = {
        chainId: "chain-defensive-1",
        documentos: [
          { id: "doc-1", tipo: "matricula" },
          { id: "doc-2", tipo: "matricula" },
        ],
        lancamentos: [
          { id: "lanc-1", documentoId: "doc-2", tipo: "registro" },
        ],
        origens: [
{ id: "ori-1", lancamentoId: "lanc-1", documentoId: "doc-1" , indice: 0},
        ],
        fimCadeias: [
          { id: "fim-1", origemId: "ori-1" },
          { id: "fim-orphan", origemId: "ori-missing" },
        ],
      };
      const json = toGraphJson(graph);
      // fim-orphan node still appears (it's a node, not an edge), but
      // its edge is skipped because the origem lookup fails.
      const fimOrphanNode = json.nodes.find((n) => n.id === "fim-orphan");
      expect(fimOrphanNode).toBeDefined();
      const fimOrphanEdge = json.edges.find((e) => e.target === "fim-orphan");
      expect(fimOrphanEdge).toBeUndefined();
    });

    it("skips fim edge when the origem's lancamento is missing", () => {
      // The `if (!lanc) continue;` guard at line 408 fires when the
      // origem references a lancamento that doesn't exist in the graph.
      const graph: TopologyGraph = {
        chainId: "chain-defensive-2",
        documentos: [
          { id: "doc-1", tipo: "matricula" },
          { id: "doc-2", tipo: "matricula" },
        ],
        lancamentos: [
          { id: "lanc-1", documentoId: "doc-2", tipo: "registro" },
        ],
        origens: [
{ id: "ori-1", lancamentoId: "lanc-1", documentoId: "doc-1" , indice: 0},
{ id: "ori-orphan", lancamentoId: "lanc-missing", documentoId: "doc-2" , indice: 0},
        ],
        fimCadeias: [
          { id: "fim-orphan", origemId: "ori-orphan" },
        ],
      };
      const json = toGraphJson(graph);
      const fimOrphanEdge = json.edges.find((e) => e.target === "fim-orphan");
      expect(fimOrphanEdge).toBeUndefined();
    });
  });
});