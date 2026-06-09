import { describe, it, expect } from "vitest";
import { hashSeed, createRng, intInRange, pick } from "../chain-topology.prng";
import {
  generateChainTopology,
  assertTopologyInvariants,
  TopologyInvariantError,
  type ChainShape,
  type TopologyGraph
} from "../chain-topology";

const SHAPES: ChainShape[] = ["linear", "branching", "merge"];

function generateRandomTriples(count: number): Array<{
  seed: number;
  shape: ChainShape;
  n: number;
}> {
  const rng = createRng(0xc0ffee);
  const triples: Array<{ seed: number; shape: ChainShape; n: number }> = [];
  for (let i = 0; i < count; i++) {
    const seed = hashSeed(`triple-${i}-${rng()}`);
    const shape = pick(SHAPES, rng);
    const minN = shape === "linear" ? 1 : 3;
    const n = intInRange(minN, 8, rng);
    triples.push({ seed, shape, n });
  }
  return triples;
}

describe("chain-topology.invariants", () => {
  describe("positive: random fuzz over (seed, shape, n)", () => {
    // Generated topologies must satisfy the structural invariants.
    const triples = generateRandomTriples(50);

    for (const { seed, shape, n } of triples) {
      it(`passes for seed=${seed}, shape=${shape}, n=${n}`, () => {
        const g: TopologyGraph = generateChainTopology(seed, n, { shape });
        expect(() => assertTopologyInvariants(g)).not.toThrow();
      });
    }
  });

  describe("invariant: document count matches n", () => {
    it("docs.length === n for every shape", () => {
      for (const shape of SHAPES) {
        for (const n of shape === "linear" ? [1, 2, 5] : [3, 5, 8]) {
          const g = generateChainTopology(7, n, { shape });
          expect(g.documentos).toHaveLength(n);
        }
      }
    });
  });

  describe("invariant: lancamentos.length === documentos.length - 1", () => {
    it("holds for linear", () => {
      // The chain is a path: each document except the first is created by
      // exactly one lancamento, so lancamentos = documents - 1.
      for (const n of [1, 2, 3, 5, 10]) {
        const g = generateChainTopology(7, n, { shape: "linear" });
        expect(g.lancamentos).toHaveLength(g.documentos.length - 1);
      }
    });

    it("holds for branching", () => {
      for (const n of [3, 4, 5, 8]) {
        const g = generateChainTopology(7, n, { shape: "branching" });
        expect(g.lancamentos).toHaveLength(g.documentos.length - 1);
      }
    });

    it("holds for merge", () => {
      // Merge has 1 merge lanc + (n-3) suffix lancs = n-2 lancs, NOT
      // n-1. The merge point consolidates 2 source docs into 1 lanc,
      // saving exactly 1 lanc compared to a linear/branching chain.
      // Cardinality is shape-specific:
      for (const n of [3, 4, 5, 8]) {
        const g = generateChainTopology(7, n, { shape: "merge" });
        expect(g.lancamentos).toHaveLength(g.documentos.length - 2);
      }
    });
    it("holds for linear and branching", () => {
      for (const shape of ["linear", "branching"] as const) {
        for (const n of [3, 4, 5, 8]) {
          const g = generateChainTopology(7, n, { shape });
          expect(g.lancamentos).toHaveLength(g.documentos.length - 1);
        }
      }
    });
  });

  describe("invariant: no duplicate IDs", () => {
    it("across all collections", () => {
      const g = generateChainTopology(42, 6, { shape: "branching" });
      const allIds = [
        ...g.documentos.map((d) => d.id),
        ...g.lancamentos.map((l) => l.id),
        ...g.origens.map((o) => o.id),
        ...g.fimCadeias.map((f) => f.id)
      ];
      expect(new Set(allIds).size).toBe(allIds.length);
    });
  });

  describe("invariant: all edge endpoints reference existing node IDs", () => {
    it("for linear, branching, and merge", () => {
      for (const shape of SHAPES) {
        const n = shape === "linear" ? 5 : 6;
        const g = generateChainTopology(42, n, { shape });
        const docIds = new Set(g.documentos.map((d) => d.id));
        const lancIds = new Set(g.lancamentos.map((l) => l.id));
        for (const l of g.lancamentos) expect(docIds.has(l.documentoId)).toBe(true);
        for (const o of g.origens) {
          expect(lancIds.has(o.lancamentoId)).toBe(true);
          expect(docIds.has(o.documentoId)).toBe(true);
        }
        const oriIds = new Set(g.origens.map((o) => o.id));
        for (const f of g.fimCadeias) expect(oriIds.has(f.origemId)).toBe(true);
      }
    });
  });

  describe("invariant: the topology is a DAG", () => {
    it("the document graph has no cycles", () => {
      for (const shape of SHAPES) {
        const n = shape === "linear" ? 5 : 6;
        const g = generateChainTopology(42, n, { shape });
        expect(() => assertTopologyInvariants(g)).not.toThrow();
      }
    });
  });

  describe("invariant: first document has no incoming edge", () => {
    it("for linear, branching, and merge", () => {
      for (const shape of SHAPES) {
        const n = shape === "linear" ? 5 : 6;
        const g = generateChainTopology(42, n, { shape });
        const incoming = new Map<string, number>();
        for (const d of g.documentos) incoming.set(d.id, 0);
        for (const l of g.lancamentos) {
          incoming.set(l.documentoId, (incoming.get(l.documentoId) ?? 0) + 1);
        }
        // The lowest-numbered doc must be the root.
        const sortedDocs = [...g.documentos].sort((a, b) => {
          const ai = parseInt(a.id.replace(/^doc-/, ""), 10);
          const bi = parseInt(b.id.replace(/^doc-/, ""), 10);
          return ai - bi;
        });
        const firstDoc = sortedDocs[0]!;
        expect(incoming.get(firstDoc.id)).toBe(0);
      }
    });
  });

  describe("negative tests", () => {
    it("assertTopologyInvariants throws on a graph with a cycle", () => {
      // Build a graph where doc-1 -> lanc-1 -> doc-2, and doc-2 -> lanc-2
      // -> doc-1. The invariant checker should detect the cycle.
      const cyclic: TopologyGraph = {
        chainId: "chain-cyclic",
        documentos: [
          { id: "doc-1", tipo: "matricula" },
          { id: "doc-2", tipo: "matricula" }
        ],
        lancamentos: [
          { id: "lanc-1", documentoId: "doc-2", tipo: "registro" },
          { id: "lanc-2", documentoId: "doc-1", tipo: "registro" }
        ],
        origens: [
          { id: "ori-1", lancamentoId: "lanc-1", documentoId: "doc-1", indice: 0 },
          { id: "ori-2", lancamentoId: "lanc-2", documentoId: "doc-2", indice: 0 }
        ],
        fimCadeias: [
          { id: "fim-1", origemId: "ori-1" },
          { id: "fim-2", origemId: "ori-2" }
        ]
      };
      expect(() => assertTopologyInvariants(cyclic)).toThrow(TopologyInvariantError);
    });

    it("assertTopologyInvariants throws on an orphan edge (lancamento references missing doc)", () => {
      const orphan: TopologyGraph = {
        chainId: "chain-orphan",
        documentos: [{ id: "doc-1", tipo: "matricula" }],
        lancamentos: [{ id: "lanc-1", documentoId: "doc-ghost", tipo: "registro" }],
        origens: [{ id: "ori-1", lancamentoId: "lanc-1", documentoId: "doc-1", indice: 0 }],
        fimCadeias: [{ id: "fim-1", origemId: "ori-1" }]
      };
      expect(() => assertTopologyInvariants(orphan)).toThrow(TopologyInvariantError);
    });

    it("assertTopologyInvariants throws on duplicate IDs", () => {
      const dup: TopologyGraph = {
        chainId: "chain-dup",
        documentos: [
          { id: "doc-1", tipo: "matricula" },
          { id: "doc-1", tipo: "matricula" }
        ],
        lancamentos: [],
        origens: [],
        fimCadeias: []
      };
      expect(() => assertTopologyInvariants(dup)).toThrow(TopologyInvariantError);
    });

    it("assertTopologyInvariants throws on a 2-doc bidirectional cycle", () => {
      // 2-doc graph where each doc points to the other via lancamentos.
      // The invariant checker should detect the cycle.
      const bad: TopologyGraph = {
        chainId: "chain-bad",
        documentos: [
          { id: "doc-1", tipo: "matricula" },
          { id: "doc-2", tipo: "matricula" }
        ],
        lancamentos: [
          { id: "lanc-1", documentoId: "doc-2", tipo: "registro" },
          { id: "lanc-2", documentoId: "doc-1", tipo: "registro" }
        ],
        origens: [
          { id: "ori-1", lancamentoId: "lanc-1", documentoId: "doc-1", indice: 0 },
          { id: "ori-2", lancamentoId: "lanc-2", documentoId: "doc-2", indice: 0 }
        ],
        fimCadeias: []
      };
      expect(() => assertTopologyInvariants(bad)).toThrow(TopologyInvariantError);
    });

    it("assertTopologyInvariants throws on a cycle in the document graph", () => {
      // 4-doc graph: doc-0 -> doc-1 -> doc-2, with a back-edge
      // doc-2 -> doc-1 (via lanc-3 targeting doc-1).
      // doc-0 is the root; the cycle is doc-1 <-> doc-2.
      // The DFS for the cycle check visits doc-0, then doc-1,
      // then doc-2, then doc-1 again (cycle hit) before any other
      // earlier invariant fires.
      const cyclic: TopologyGraph = {
        chainId: "chain-cycle",
        documentos: [
          { id: "doc-0", tipo: "matricula" },
          { id: "doc-1", tipo: "matricula" },
          { id: "doc-2", tipo: "matricula" }
        ],
        lancamentos: [
          { id: "lanc-1", documentoId: "doc-1", tipo: "registro" },
          { id: "lanc-2", documentoId: "doc-2", tipo: "registro" },
          { id: "lanc-3", documentoId: "doc-1", tipo: "registro" } // back-edge
        ],
        origens: [
          { id: "ori-1", lancamentoId: "lanc-1", documentoId: "doc-0", indice: 0 },
          { id: "ori-2", lancamentoId: "lanc-2", documentoId: "doc-1", indice: 0 },
          { id: "ori-3", lancamentoId: "lanc-3", documentoId: "doc-2", indice: 0 }
        ],
        fimCadeias: []
      };
      expect(() => assertTopologyInvariants(cyclic)).toThrow(/cycle/i);
    });

    it("assertTopologyInvariants throws on a rootless graph (no root document)", () => {
      // 2-doc graph where both docs have an incoming lancamento
      // (via the cross-coupling). rootCount = 0, so the
      // "no root" check fires.
      const rootless: TopologyGraph = {
        chainId: "chain-rootless",
        documentos: [
          { id: "doc-0", tipo: "matricula" },
          { id: "doc-1", tipo: "matricula" }
        ],
        lancamentos: [
          { id: "lanc-1", documentoId: "doc-1", tipo: "registro" },
          { id: "lanc-2", documentoId: "doc-0", tipo: "registro" }
        ],
        origens: [
          { id: "ori-1", lancamentoId: "lanc-1", documentoId: "doc-0", indice: 0 },
          { id: "ori-2", lancamentoId: "lanc-2", documentoId: "doc-1", indice: 0 }
        ],
        fimCadeias: [
          { id: "fim-1", origemId: "ori-1" },
          { id: "fim-2", origemId: "ori-2" }
        ]
      };
      expect(() => assertTopologyInvariants(rootless)).toThrow(/no root/i);
    });

    it("assertTopologyInvariants throws when a terminal origem has zero fims", () => {
      // Linear 2-doc chain. ori-1 (target doc-2, terminal) has 0 fims.
      // The terminal-must-have-1-fim check (line 588) should fire.
      const noFim: TopologyGraph = {
        chainId: "chain-no-fim",
        documentos: [
          { id: "doc-1", tipo: "matricula" },
          { id: "doc-2", tipo: "matricula" }
        ],
        lancamentos: [{ id: "lanc-1", documentoId: "doc-2", tipo: "registro" }],
        origens: [{ id: "ori-1", lancamentoId: "lanc-1", documentoId: "doc-1", indice: 0 }],
        fimCadeias: []
      };
      expect(() => assertTopologyInvariants(noFim)).toThrow(/must have exactly 1 fim/i);
    });

    it("assertTopologyInvariants throws when a non-terminal origem has a fim", () => {
      // 3-doc linear chain. ori-1 targets doc-2 which has doc-3 as a
      // successor (via lanc-2), so ori-1 is non-terminal. Giving it a
      // fim triggers line 594.
      const extraFim: TopologyGraph = {
        chainId: "chain-extra-fim",
        documentos: [
          { id: "doc-1", tipo: "matricula" },
          { id: "doc-2", tipo: "matricula" },
          { id: "doc-3", tipo: "matricula" }
        ],
        lancamentos: [
          { id: "lanc-1", documentoId: "doc-2", tipo: "registro" },
          { id: "lanc-2", documentoId: "doc-3", tipo: "registro" }
        ],
        origens: [
          { id: "ori-1", lancamentoId: "lanc-1", documentoId: "doc-1", indice: 0 },
          { id: "ori-2", lancamentoId: "lanc-2", documentoId: "doc-2", indice: 0 }
        ],
        fimCadeias: [
          { id: "fim-1", origemId: "ori-1" },
          { id: "fim-2", origemId: "ori-2" }
        ]
      };
      expect(() => assertTopologyInvariants(extraFim)).toThrow(/must have 0 fim/i);
    });

    it("assertTopologyInvariants throws when a Registro has zero origens", () => {
      // Line 504: registro lanc with no origens → S-3 violation.
      // Need valid S-5 setup: chain doc-1 -> doc-2 (terminal).
      // Then add a 3rd doc with a lanc that has 0 origens.
      const registroSemOrigem: TopologyGraph = {
        chainId: "chain-registro-sem-origem",
        documentos: [
          { id: "doc-1", tipo: "matricula" },
          { id: "doc-2", tipo: "matricula" },
          { id: "doc-3", tipo: "matricula" }
        ],
        lancamentos: [
          { id: "lanc-1", documentoId: "doc-2", tipo: "registro" },
          { id: "lanc-2", documentoId: "doc-3", tipo: "registro" }
        ],
        origens: [
          { id: "ori-1", lancamentoId: "lanc-1", documentoId: "doc-1", indice: 0 }
          // lanc-2 has no origem → S-3 violation
        ],
        fimCadeias: [{ id: "fim-1", origemId: "ori-1" }]
      };
      expect(() => assertTopologyInvariants(registroSemOrigem)).toThrow(
        /must have at least 1 origem/i
      );
    });

    it("assertTopologyInvariants throws when an Averbação has origens", () => {
      // Line 498: averbação lanc with origens → S-3 violation.
      const averbacaoComOrigem: TopologyGraph = {
        chainId: "chain-averbacao-com-origem",
        documentos: [
          { id: "doc-1", tipo: "matricula" },
          { id: "doc-2", tipo: "matricula" }
        ],
        lancamentos: [{ id: "lanc-1", documentoId: "doc-2", tipo: "averbacao" }],
        origens: [{ id: "ori-1", lancamentoId: "lanc-1", documentoId: "doc-1", indice: 0 }],
        fimCadeias: []
      };
      expect(() => assertTopologyInvariants(averbacaoComOrigem)).toThrow(
        /averbação.*must have 0 origens/i
      );
    });

    it("assertTopologyInvariants throws on duplicate lancamento id", () => {
      const dupLanc: TopologyGraph = {
        chainId: "chain-dup-lanc",
        documentos: [
          { id: "doc-1", tipo: "matricula" },
          { id: "doc-2", tipo: "matricula" }
        ],
        lancamentos: [
          { id: "lanc-1", documentoId: "doc-2", tipo: "registro" },
          { id: "lanc-1", documentoId: "doc-1", tipo: "registro" }
        ],
        origens: [{ id: "ori-1", lancamentoId: "lanc-1", documentoId: "doc-1", indice: 0 }],
        fimCadeias: [{ id: "fim-1", origemId: "ori-1" }]
      };
      expect(() => assertTopologyInvariants(dupLanc)).toThrow(/duplicate lancamento id/i);
    });

    it("assertTopologyInvariants throws on duplicate origem id", () => {
      const dupOri: TopologyGraph = {
        chainId: "chain-dup-ori",
        documentos: [
          { id: "doc-1", tipo: "matricula" },
          { id: "doc-2", tipo: "matricula" }
        ],
        lancamentos: [{ id: "lanc-1", documentoId: "doc-2", tipo: "registro" }],
        origens: [
          { id: "ori-1", lancamentoId: "lanc-1", documentoId: "doc-1", indice: 0 },
          { id: "ori-1", lancamentoId: "lanc-1", documentoId: "doc-1", indice: 1 }
        ],
        fimCadeias: [{ id: "fim-1", origemId: "ori-1" }]
      };
      expect(() => assertTopologyInvariants(dupOri)).toThrow(/duplicate origem id/i);
    });

    it("assertTopologyInvariants throws on duplicate fim_cadeia id", () => {
      const dupFim: TopologyGraph = {
        chainId: "chain-dup-fim",
        documentos: [
          { id: "doc-1", tipo: "matricula" },
          { id: "doc-2", tipo: "matricula" }
        ],
        lancamentos: [{ id: "lanc-1", documentoId: "doc-2", tipo: "registro" }],
        origens: [{ id: "ori-1", lancamentoId: "lanc-1", documentoId: "doc-1", indice: 0 }],
        fimCadeias: [
          { id: "fim-1", origemId: "ori-1" },
          { id: "fim-1", origemId: "ori-1" }
        ]
      };
      expect(() => assertTopologyInvariants(dupFim)).toThrow(/duplicate fim_cadeia id/i);
    });

    it("assertTopologyInvariants throws when an origem references a missing lancamento", () => {
      const danglingOri: TopologyGraph = {
        chainId: "chain-dangling-ori",
        documentos: [
          { id: "doc-1", tipo: "matricula" },
          { id: "doc-2", tipo: "matricula" }
        ],
        lancamentos: [{ id: "lanc-1", documentoId: "doc-2", tipo: "registro" }],
        origens: [{ id: "ori-1", lancamentoId: "lanc-missing", documentoId: "doc-1", indice: 0 }],
        fimCadeias: []
      };
      expect(() => assertTopologyInvariants(danglingOri)).toThrow(/references missing lancamento/i);
    });

    it("assertTopologyInvariants throws when an origem references a missing documento", () => {
      const danglingDoc: TopologyGraph = {
        chainId: "chain-dangling-doc",
        documentos: [
          { id: "doc-1", tipo: "matricula" },
          { id: "doc-2", tipo: "matricula" }
        ],
        lancamentos: [{ id: "lanc-1", documentoId: "doc-2", tipo: "registro" }],
        origens: [{ id: "ori-1", lancamentoId: "lanc-1", documentoId: "doc-ghost", indice: 0 }],
        fimCadeias: []
      };
      expect(() => assertTopologyInvariants(danglingDoc)).toThrow(
        /origem.*references missing documento/i
      );
    });

    it("assertTopologyInvariants throws when a fim_cadeia references a missing origem", () => {
      const danglingFim: TopologyGraph = {
        chainId: "chain-dangling-fim",
        documentos: [
          { id: "doc-1", tipo: "matricula" },
          { id: "doc-2", tipo: "matricula" }
        ],
        lancamentos: [{ id: "lanc-1", documentoId: "doc-2", tipo: "registro" }],
        origens: [{ id: "ori-1", lancamentoId: "lanc-1", documentoId: "doc-1", indice: 0 }],
        fimCadeias: [{ id: "fim-1", origemId: "ori-missing" }]
      };
      expect(() => assertTopologyInvariants(danglingFim)).toThrow(
        /fim_cadeia.*references missing origem/i
      );
    });

    it("assertTopologyInvariants throws when origens have non-contiguous indices", () => {
      // [0, 2] (gap at 1) — should fail the contiguity check.
      // Acyclic graph: doc-0 -> doc-2, doc-1 -> doc-2 (two sources to same target)
      // Both origens point to the SAME lancamento (lanc-1) with indices 0 and 2.
      const gapIndices: TopologyGraph = {
        chainId: "chain-gap",
        documentos: [
          { id: "doc-0", tipo: "matricula" },
          { id: "doc-1", tipo: "matricula" },
          { id: "doc-2", tipo: "matricula" }
        ],
        lancamentos: [{ id: "lanc-1", documentoId: "doc-2", tipo: "registro" }],
        origens: [
          { id: "ori-1", lancamentoId: "lanc-1", documentoId: "doc-0", indice: 0 },
          { id: "ori-2", lancamentoId: "lanc-1", documentoId: "doc-1", indice: 2 } // gap at index 1
        ],
        fimCadeias: []
      };
      expect(() => assertTopologyInvariants(gapIndices)).toThrow(/non-contiguous indices/i);
    });

    it("assertTopologyInvariants throws when origens have duplicate indices", () => {
      // Indices [0, 0] — duplicate.
      // Acyclic graph: doc-0 -> doc-2, doc-1 -> doc-2 (two sources to same target)
      // Both origens point to the SAME lancamento with index 0.
      const dupIndices: TopologyGraph = {
        chainId: "chain-dup-idx",
        documentos: [
          { id: "doc-0", tipo: "matricula" },
          { id: "doc-1", tipo: "matricula" },
          { id: "doc-2", tipo: "matricula" }
        ],
        lancamentos: [{ id: "lanc-1", documentoId: "doc-2", tipo: "registro" }],
        origens: [
          { id: "ori-1", lancamentoId: "lanc-1", documentoId: "doc-0", indice: 0 },
          { id: "ori-2", lancamentoId: "lanc-1", documentoId: "doc-1", indice: 0 } // duplicate index 0
        ],
        fimCadeias: []
      };
      expect(() => assertTopologyInvariants(dupIndices)).toThrow(/non-contiguous indices/i);
    });

    it("assertTopologyInvariants throws when multiple origens in the same lancamento reference the same documentoId", () => {
      // This is the edge case flagged by Greptile: two origens in the same
      // lancamento sharing a documentoId (indices 0 and 1 are contiguous,
      // so the contiguity check passes). The toGraphJson edge ID scheme
      // ${documentoId}->${lancamentoId} would produce duplicate edge IDs,
      // causing validateGraph to throw a confusing "Duplicate edge ID" error.
      // The invariant checker must catch this with a clear diagnostic.
      const dupDocumentoId: TopologyGraph = {
        chainId: "chain-dup-docid",
        documentos: [
          { id: "doc-0", tipo: "matricula" },
          { id: "doc-1", tipo: "matricula" },
          { id: "doc-2", tipo: "matricula" }
        ],
        lancamentos: [{ id: "lanc-1", documentoId: "doc-2", tipo: "registro" }],
        origens: [
          { id: "ori-1", lancamentoId: "lanc-1", documentoId: "doc-0", indice: 0 },
          { id: "ori-2", lancamentoId: "lanc-1", documentoId: "doc-0", indice: 1 } // SAME documentoId, different index
        ],
        fimCadeias: []
      };
      expect(() => assertTopologyInvariants(dupDocumentoId)).toThrow(
        /multiple origens referencing the same documento.*would produce duplicate edge IDs/i
      );
    });

    it("assertTopologyInvariants throws on an orphan graph (2+ documentos, 0 lancamentos)", () => {
      // Pre-PR bug: the orphan-documento check loop was a no-op, so a
      // graph with two disconnected documentos and zero lancamentos
      // would pass the root check (rootCount >= 1) but violate the
      // single-chain connectivity contract. The fix adds an explicit
      // "n > 1 lancamentos >= 1" check.
      const orphan: TopologyGraph = {
        chainId: "chain-orphan-lanc",
        documentos: [
          { id: "doc-1", tipo: "matricula" },
          { id: "doc-2", tipo: "matricula" }
        ],
        lancamentos: [],
        origens: [],
        fimCadeias: []
      };
      expect(() => assertTopologyInvariants(orphan)).toThrow(
        /orphan graph.*0 lancamentos/i
      );
    });

    it("assertTopologyInvariants allows a single isolated documento (linear n=1)", () => {
      // n=1 linear legitimately produces a graph with one doc,
      // zero lancamentos, zero origens, zero fims. This is not
      // an orphan — it's the degenerate single-doc case. The
      // "orphan" check should NOT fire here.
      const single: TopologyGraph = {
        chainId: "chain-single",
        documentos: [{ id: "doc-1", tipo: "matricula" }],
        lancamentos: [],
        origens: [],
        fimCadeias: []
      };
      expect(() => assertTopologyInvariants(single)).not.toThrow();
    });

    it("assertTopologyInvariants throws on a cross-collection node id collision", () => {
      // Pre-PR bug: duplicate-id checks were per-collection. A
      // documento id that equals a lancamento id (or fim id) would
      // pass invariants but produce a `validateGraph` failure with
      // a confusing "Duplicate edge ID" error. The fix adds a
      // global node-id uniqueness check.
      // Set up a graph that satisfies the S-3/S-5 contracts (registro
      // has >= 1 origem, indices contiguous, terminal origem has a
      // fim) but has a colliding node id between collections.
      const collision: TopologyGraph = {
        chainId: "chain-collision",
        documentos: [
          { id: "shared-id", tipo: "matricula" },
          { id: "doc-2", tipo: "matricula" }
        ],
        lancamentos: [{ id: "shared-id", documentoId: "doc-2", tipo: "registro" }],
        origens: [{ id: "ori-1", lancamentoId: "shared-id", documentoId: "shared-id", indice: 0 }],
        fimCadeias: [{ id: "fim-1", origemId: "ori-1" }]
      };
      expect(() => assertTopologyInvariants(collision)).toThrow(
        /node id shared-id \(lancamento\) collides/i
      );
    });
  });
});
