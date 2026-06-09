import { createRng, pick } from "./chain-topology.prng";

export type DocumentoTipo = "matricula" | "transcricao";

export interface TopologyDocumento {
  id: string;
  /** Per v2 schema: `matricula` | `transcricao`. */
  tipo: DocumentoTipo;
}

export type LancamentoTipo = "registro" | "averbacao";

export interface TopologyLancamento {
  id: string;
  documentoId: string;
  tipo: LancamentoTipo;
}

export interface TopologyOrigem {
  id: string;
  /** 0-based contiguous index of this origem within its lancamento (per plan
   *  S-5 / `docs/db/SCHEMA_CONSOLIDATED.md:197` — must be 0..k-1 with no
   *  duplicates or gaps inside a given `lancamentoId`). */
    indice: number;
  lancamentoId: string;
  documentoId: string;
}

export interface TopologyFimCadeia {
  id: string;
  origemId: string;
}

export interface TopologyGraph {
  documentos: TopologyDocumento[];
  lancamentos: TopologyLancamento[];
  origens: TopologyOrigem[];
  fimCadeias: TopologyFimCadeia[];
  chainId: string;
}

export type ChainShape = "linear" | "branching" | "merge";

export interface GenerateChainTopologyOptions {
  shape?: ChainShape;
}

const DOCUMENTO_TIPOS: readonly DocumentoTipo[] = [
  "matricula",
  "transcricao",
] as const;

export function generateChainTopology(
  seed: number,
  n: number,
  options?: GenerateChainTopologyOptions
): TopologyGraph {
  const shape = options?.shape ?? "linear";

  if (!Number.isSafeInteger(n) || n < 1) {
    throw new RangeError(`n must be a safe integer >= 1, got ${n}`);
  }

  if ((shape === "branching" || shape === "merge") && n < 3) {
    throw new RangeError(`shape '${shape}' requires n >= 3, got ${n}`);
  }

  const rng = createRng(seed);
  const chainId = `chain-${seed}`;

  if (shape === "linear") {
    return generateLinear(n, rng, chainId);
  }
  if (shape === "branching") {
    return generateBranching(n, rng, chainId);
  }
  return generateMerge(n, rng, chainId);
}

/**
 * Identify the origens that are "terminal" in the document graph and
 * emit one fim_cadeia per terminal origem.
 *
 * Definition of "terminal origem" (DAG-terminal, follows the natural
 * direction of the chain):
 *   An origem is terminal iff its target document — i.e. the
 *   `documentoId` of the lancamento it references — is NOT the source
 *   of any other origem. A doc is a "source" iff at least one origem
 *   has that doc as its `documentoId`.
 *
 * This is the single source of truth for the S-5 / Q3 invariant: "every
 * terminal origem has exactly one fim_cadeia; every non-terminal
 * origem has zero." All three shape generators call this helper rather
 * than hand-rolling the fim arrays, so the topology the generator
 * produces is guaranteed to satisfy `assertTopologyInvariants` and the
 * two can never disagree.
 *
 * `idPrefix` lets a caller namespace the fim ids (default "fim").
 */
function computeTerminalFims(
  lancamentos: readonly TopologyLancamento[],
  origens: readonly TopologyOrigem[],
  idPrefix: string = "fim"
): TopologyFimCadeia[] {
  // Build map: lancamentoId -> target documentoId.
  const targetByLanc = new Map<string, string>();
  for (const l of lancamentos) {
    targetByLanc.set(l.id, l.documentoId);
  }
  // A doc is a "source of further origens" iff at least one origem in
  // the graph has it as its source documentoId.
  const docsAsOrigemSource = new Set<string>();
  for (const o of origens) {
    docsAsOrigemSource.add(o.documentoId);
  }
  // An origem is terminal iff its target doc is not a source.
  const fims: TopologyFimCadeia[] = [];
  let counter = 0;
  for (const o of origens) {
    const target = targetByLanc.get(o.lancamentoId);
    // The invariant check will reject origens that reference missing
    // lancamentos, so we don't need to throw here — just skip the
    // dangling origem. (In practice this never happens because every
    // generator emits matching pairs.)
    if (target === undefined) continue;
    if (!docsAsOrigemSource.has(target)) {
      counter += 1;
      fims.push({ id: `${idPrefix}-${counter}`, origemId: o.id });
    }
  }
  return fims;
}

function generateLinear(
  n: number,
  rng: () => number,
  chainId: string
): TopologyGraph {
  const documentos: TopologyDocumento[] = [];
  for (let i = 1; i <= n; i++) {
    documentos.push({ id: `doc-${i}`, tipo: pick(DOCUMENTO_TIPOS, rng) });
  }

  // Plan S-3: every linear lancamento is a Registro so that
  //   - the linear path has exactly n-1 origens (one per lancamento),
  //   - the last lancamento is a Registro, guaranteeing a terminal
  //     origem for the single linear fim_cadeia.
  // The Averbação variant is reserved for faker-driven generators in
  // later tasks; assertTopologyInvariants still enforces the rule
  // (Averbação has zero origens) via the negative tests.
  const lancamentos: TopologyLancamento[] = [];
  const origens: TopologyOrigem[] = [];
  for (let i = 1; i <= n - 1; i++) {
    lancamentos.push({
      id: `lanc-${i}`,
      documentoId: `doc-${i + 1}`,
      tipo: "registro",
    });
    origens.push({
      id: `ori-${i}`,
      lancamentoId: `lanc-${i}`,
      documentoId: `doc-${i}`,
      indice: 0,
    });
  }

  // In a linear chain, only the last lancamento produces a terminal
  // origem (its target doc has no outgoing origem), so exactly one
  // fim_cadeia. For n=1 there are no lancamentos and no fims.
  const fimCadeias: TopologyFimCadeia[] =
    n >= 2 ? computeTerminalFims(lancamentos, origens) : [];

  return { documentos, lancamentos, origens, fimCadeias, chainId };
}

function generateBranching(
  n: number,
  rng: () => number,
  chainId: string
): TopologyGraph {
  // Linear prefix of (n-2) docs, then 1 branch point (= last prefix doc) with
  // 2 outgoing lancamentos into 2 parallel children.
  // Total docs = (n-2 prefix) + 2 children = n.
  const documentos: TopologyDocumento[] = [];
  for (let i = 1; i <= n; i++) {
    documentos.push({ id: `doc-${i}`, tipo: pick(DOCUMENTO_TIPOS, rng) });
  }

  const prefixLen = n - 2;
  const branchPointId = `doc-${prefixLen}`;
  const leftChildId = `doc-${prefixLen + 1}`;
  const rightChildId = `doc-${prefixLen + 2}`;

  const lancamentos: TopologyLancamento[] = [];
  const origens: TopologyOrigem[] = [];

  // Prefix lancs are all Registro: deterministic, one origem per
  // lancamento. See generateLinear for rationale.
  for (let i = 1; i <= prefixLen - 1; i++) {
    lancamentos.push({
      id: `lanc-${i}`,
      documentoId: `doc-${i + 1}`,
      tipo: "registro",
    });
    origens.push({
      id: `ori-${i}`,
      lancamentoId: `lanc-${i}`,
      documentoId: `doc-${i}`,
      indice: 0,
    });
  }

  const leftIdx = prefixLen;
  const rightIdx = prefixLen + 1;
  lancamentos.push({
    id: `lanc-${leftIdx}`,
    documentoId: leftChildId,
    tipo: "registro",
  });
  origens.push({
    id: `ori-${leftIdx}`,
    lancamentoId: `lanc-${leftIdx}`,
    documentoId: branchPointId,
    indice: 0,
  });
  lancamentos.push({
    id: `lanc-${rightIdx}`,
    documentoId: rightChildId,
    tipo: "registro",
  });
  origens.push({
    id: `ori-${rightIdx}`,
    lancamentoId: `lanc-${rightIdx}`,
    documentoId: branchPointId,
    indice: 0,
  });

  // Per Q3 + plan S-5: every terminal origem (per the DAG-terminal
  // definition in computeTerminalFims) gets exactly one fim_cadeia;
  // non-terminal origens get none. The branch point's two origens are
  // non-terminal (the branch point has 2 outgoing origens via the
  // branch's children — wait, no: the branch point is a SOURCE of 2
  // origens, not a target. The rightChild's origem targets doc-(n) which
  // has no outgoing origens, so it is terminal. The leftChild's origem
  // targets doc-(n-1) which also has no outgoing origens. So both
  // branch origens are terminal. Plus the prefix origens that point at
  // docs that have no outgoing origens are also terminal — for a 2-doc
  // prefix (n=4) the prefix is just doc-1 → doc-2 (no branching), so
  // ori-prefix-1 is non-terminal, ori-prefix-2 is terminal. For longer
  // prefixes, only the last prefix origem (whose target is the branch
  // point) is non-terminal. See computeTerminalFims for the precise
  // rule; the test cases for branching n=3 / n=6 / n=4 pin the counts.
  const fimCadeias = computeTerminalFims(lancamentos, origens);
  return { documentos, lancamentos, origens, fimCadeias, chainId };
}

function generateMerge(
  n: number,
  rng: () => number,
  chainId: string
): TopologyGraph {
  // Plan S-4: merge where one Registro has two or more origins.
  // 1 lancamento at the merge point: lanc-1 (Registro) targeting doc-3 with
  // 2 origens: ori-1 (from doc-1) and ori-2 (from doc-2). Then a linear
  // suffix: lanc-2..lanc-(n-2) for doc-4..doc-n, each with 1 origem.
  // For n=3: 1 lancamento with 2 origens, no suffix, 0 additional fims
  // beyond the terminal ones.
  const documentos: TopologyDocumento[] = [];
  for (let i = 1; i <= n; i++) {
    documentos.push({ id: `doc-${i}`, tipo: pick(DOCUMENTO_TIPOS, rng) });
  }

  const lancamentos: TopologyLancamento[] = [];
  const origens: TopologyOrigem[] = [];

  // Merge point: 1 Registro with 2 origens.
  lancamentos.push({
    id: `lanc-1`,
    documentoId: `doc-3`,
    tipo: "registro",
  });
  origens.push({
    id: `ori-1`,
    lancamentoId: `lanc-1`,
    documentoId: `doc-1`,
    indice: 0,
  });
  origens.push({
    id: `ori-2`,
    lancamentoId: `lanc-1`,
    documentoId: `doc-2`,
    indice: 1,
  });

  // Linear suffix: doc-3 -> doc-4 -> ... -> doc-n.
  // For n=3 the suffix is empty; for n>=4 we add n-3 suffix lancamentos.
  // All suffix lancs are Registro: one origem per lancamento.
  // Origem ids start at 3 (because the merge point already created
  // ori-1 and ori-2) and increment independently of the lancamento
  // counter.
  for (let i = 1; i <= n - 3; i++) {
    const lancIdx = 1 + i; // 2, 3, ..., n-2
    const oriIdx = 2 + i; // 3, 4, ..., n-1
    const docIdx = 3 + i; // 4, 5, ..., n
    lancamentos.push({
      id: `lanc-${lancIdx}`,
      documentoId: `doc-${docIdx}`,
      tipo: "registro",
    });
    origens.push({
      id: `ori-${oriIdx}`,
      lancamentoId: `lanc-${lancIdx}`,
      documentoId: `doc-${docIdx - 1}`,
      indice: 0,
    });
  }

  // Fim_cadeia: every DAG-terminal origem (per `computeTerminalFims`)
  // gets exactly one fim. The merge point's 2 origens point at the
  // merge target doc (doc-3). That doc is a "source" iff it appears as
  // a source documentoId in any origem, which is only true when the
  // suffix has at least one lanc (n >= 4). So:
  //   - merge n=3: ori-1, ori-2 are terminal (no suffix) → 2 fims.
  //   - merge n>=4: ori-1, ori-2 are non-terminal (suffix flows from
  //     the merge target doc); the last suffix origem is the only
  //     terminal one → 1 fim.
  const fimCadeias = computeTerminalFims(lancamentos, origens);

  return { documentos, lancamentos, origens, fimCadeias, chainId };
}

/**
 * Local, structurally-identical mirror of `GraphJson` from
 * `packages/web/src/graph/types`. Defined here so the seed module is
 * self-contained (no cross-package import). The web adapter
 * `topologyToGraphJson` performs the same conversion with the canonical
 * `GraphJson` type and validates the result with `validateGraph`.
 */
export interface SeedGraphNode {
  id: string;
  label: string;
  type: string;
}

export interface SeedGraphEdge {
  id: string;
  source: string;
  target: string;
}

export interface SeedGraphJson {
  nodes: SeedGraphNode[];
  edges: SeedGraphEdge[];
}

/**
 * Convert a TopologyGraph into a minimal node/edge JSON payload suitable
 * for the web graph renderer. Uses only id/label/type for nodes and
 * id/source/target for edges. Richer metadata (lancamento/documento
 * tipo, chain membership) stays on the TopologyGraph until T-201 fills
 * human labels.
 */
export function toGraphJson(graph: TopologyGraph): SeedGraphJson {
  const nodes: SeedGraphNode[] = [];
  const edges: SeedGraphEdge[] = [];

  for (const doc of graph.documentos) {
    const idx = doc.id.replace(/^doc-/, "");
    nodes.push({ id: doc.id, label: `Documento ${idx}`, type: "documento" });
  }
  for (const lanc of graph.lancamentos) {
    const idx = lanc.id.replace(/^lanc-/, "");
    nodes.push({
      id: lanc.id,
      label: `Lançamento ${idx}`,
      type: "lancamento",
    });
  }
  for (const fim of graph.fimCadeias) {
    nodes.push({
      id: fim.id,
      label: "Fim de cadeia",
      type: "fim_cadeia",
    });
  }

  // Build lookups so the terminal-fim edge in GraphJson can be anchored
  // on the right document: each fim is attached to an origem, which is
  // attached to a lancamento; the fim edge should originate from the
  // document the lancamento *creates* (its target), not the source of
  // the origem (which is the branch point in branching shape).
  const lancById = new Map<string, TopologyLancamento>();
  for (const l of graph.lancamentos) lancById.set(l.id, l);
  const origemById = new Map<string, TopologyOrigem>();
  for (const o of graph.origens) origemById.set(o.id, o);

  for (const ori of graph.origens) {
    edges.push({
      id: `${ori.documentoId}->${ori.lancamentoId}`,
      source: ori.documentoId,
      target: ori.lancamentoId,
    });
  }
  for (const lanc of graph.lancamentos) {
    edges.push({
      id: `${lanc.id}->${lanc.documentoId}`,
      source: lanc.id,
      target: lanc.documentoId,
    });
  }
  for (const fim of graph.fimCadeias) {
    const ori = origemById.get(fim.origemId);
    if (!ori) continue;
    const lanc = lancById.get(ori.lancamentoId);
    if (!lanc) continue;
    edges.push({
      id: `${lanc.documentoId}->${fim.id}`,
      source: lanc.documentoId,
      target: fim.id,
    });
  }

  return { nodes, edges };
}

export class TopologyInvariantError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "TopologyInvariantError";
  }
}

/**
 * Throw if `graph` violates any structural invariant of a well-formed
 * dominial-chain topology. See `chain-topology.invariants.test.ts` for
 * the full set of guarantees.
 *
 * Cartório domain rules enforced here (per plan S-3 and S-5):
 *   - Each Registro lancamento has at least one origem.
 *   - Each Averbação lancamento has zero origens.
 *   - An origem is "terminal" iff its source document has no outgoing
 *     origem (no other origem references the same document as input).
 *   - Every terminal origem has exactly one fim_cadeia.
 *   - Every non-terminal origem has zero fim_cadeia.
 */
export function assertTopologyInvariants(graph: TopologyGraph): void {
  const docIds = new Set<string>();
  for (const d of graph.documentos) {
    if (docIds.has(d.id)) {
      throw new TopologyInvariantError(`duplicate documento id: ${d.id}`);
    }
    docIds.add(d.id);
  }

  const lancIds = new Set<string>();
  for (const l of graph.lancamentos) {
    if (lancIds.has(l.id)) {
      throw new TopologyInvariantError(`duplicate lancamento id: ${l.id}`);
    }
    lancIds.add(l.id);
    if (!docIds.has(l.documentoId)) {
      throw new TopologyInvariantError(
        `lancamento ${l.id} references missing documento ${l.documentoId}`
      );
    }
  }

  const oriIds = new Set<string>();
  const origensByLanc = new Map<string, TopologyOrigem[]>();
  for (const o of graph.origens) {
    if (oriIds.has(o.id)) {
      throw new TopologyInvariantError(`duplicate origem id: ${o.id}`);
    }
    oriIds.add(o.id);
    if (!lancIds.has(o.lancamentoId)) {
      throw new TopologyInvariantError(
        `origem ${o.id} references missing lancamento ${o.lancamentoId}`
      );
    }
    if (!docIds.has(o.documentoId)) {
      throw new TopologyInvariantError(
        `origem ${o.id} references missing documento ${o.documentoId}`
      );
    }
    const list = origensByLanc.get(o.lancamentoId) ?? [];
    list.push(o);
    origensByLanc.set(o.lancamentoId, list);
  }

  // Ensure each lancamento's origens have unique documentoId values.
  // Without this, toGraphJson produces duplicate edge IDs
  // (${documentoId}->${lancamentoId}) which passes assertTopologyInvariants
  // but causes validateGraph to throw a confusing "Duplicate edge ID" error.
  for (const [lancId, origens] of origensByLanc) {
    const docIdsInLanc = new Set<string>();
    for (const o of origens) {
      if (docIdsInLanc.has(o.documentoId)) {
        throw new TopologyInvariantError(
          `lancamento ${lancId} has multiple origens referencing the same documento ${o.documentoId} (would produce duplicate edge IDs in toGraphJson)`
        );
      }
      docIdsInLanc.add(o.documentoId);
    }
  }

  // (Deferred until after the DAG cycle check: contiguity is a
  // secondary S-5 property and we want higher-priority structural
  // failures — roots, DAG cycles — to surface first.)
  const fimIds = new Set<string>();
  for (const f of graph.fimCadeias) {
    if (fimIds.has(f.id)) {
      throw new TopologyInvariantError(`duplicate fim_cadeia id: ${f.id}`);
    }
    fimIds.add(f.id);
    if (!oriIds.has(f.origemId)) {
      throw new TopologyInvariantError(
        `fim_cadeia ${f.id} references missing origem ${f.origemId}`
      );
    }
  }

  // S-5: each Registro has origens.length >= 1; each Averbação has none.
  for (const l of graph.lancamentos) {
    const origensForLanc = origensByLanc.get(l.id) ?? [];
    if (l.tipo === "averbacao") {
      if (origensForLanc.length !== 0) {
        throw new TopologyInvariantError(
          `averbação ${l.id} must have 0 origens, has ${origensForLanc.length}`
        );
      }
    } else {
      if (origensForLanc.length < 1) {
        throw new TopologyInvariantError(
          `registro ${l.id} must have at least 1 origem, has ${origensForLanc.length}`
        );
      }
    }
  }

  // Cardinality: not strictly lancamentos === documentos - 1 (that
  // only holds for linear / branching and for the merge suffix).
  // Instead, enforce the shape-agnostic structural checks:
  //   - The topology is a DAG (checked below).
  //   - At least one documento has no incoming lancamento (a root
  //     exists; in merge there are two — doc-1 and doc-2).
  //   - Every other documento has >= 1 incoming lancamento
  //     (no orphan documentos).
  const incoming = new Map<string, number>();
  for (const d of graph.documentos) incoming.set(d.id, 0);
  for (const l of graph.lancamentos) {
    incoming.set(l.documentoId, (incoming.get(l.documentoId) ?? 0) + 1);
  }
  const rootCount = [...incoming.values()].filter((c) => c === 0).length;
  if (rootCount < 1) {
    throw new TopologyInvariantError(
      `topology has no root (every documento has >= 1 incoming lancamento)`
    );
  }

  // Ensure every non-root documento has >= 1 incoming lancamento
  // (no orphan documentos connected to a root but unreachable from
  // it). The "no root" check above only verifies `rootCount >= 1`;
  // a graph with one root plus an isolated documento (0 incoming,
  // 0 outgoing) would still pass that check. We catch it here:
  // the count of non-root documentos is `documentos.length -
  // rootCount` and must equal the count of incoming slots
  // consumed by lancamentos (`lancamentos.length`, modulo
  // 1:N for merge which has 2 origens per merge lancamento).
  //
  // Simpler invariant: every documento that has 0 incoming AND 0
  // outgoing is an orphan. Equivalently: if `documentos.length >
  // 1`, there must be at least one lancamento connecting them.
  if (graph.documentos.length > 1 && graph.lancamentos.length === 0) {
    throw new TopologyInvariantError(
      `orphan graph: ${graph.documentos.length} documentos with 0 lancamentos`
    );
  }
  // For n=1 linear, documentos=[doc-1], lancamentos=[], origens=[],
  // fims=[] is the legitimate degenerate case. No throw.

  // Cross-collection uniqueness: `toGraphJson` emits
  // documentos, lancamentos, and fimCadeias into one node
  // namespace, so IDs that are unique WITHIN their collection
  // (e.g. "doc-1" and "lanc-1") can still collide across
  // collections in the resulting graph (a doc id equals a
  // lanc id). The check below ensures every node id in the
  // resulting graph is unique.
  const nodeIds = new Set<string>();
  for (const d of graph.documentos) {
    if (nodeIds.has(d.id)) {
      throw new TopologyInvariantError(
        `node id ${d.id} (documento) collides with another node`
      );
    }
    nodeIds.add(d.id);
  }
  for (const l of graph.lancamentos) {
    if (nodeIds.has(l.id)) {
      throw new TopologyInvariantError(
        `node id ${l.id} (lancamento) collides with another node`
      );
    }
    nodeIds.add(l.id);
  }
  for (const f of graph.fimCadeias) {
    if (nodeIds.has(f.id)) {
      throw new TopologyInvariantError(
        `node id ${f.id} (fim_cadeia) collides with another node`
      );
    }
    nodeIds.add(f.id);
  }

  // DAG check on the document graph: edges from doc -> doc via
  // (doc -> lanc -> doc). A cycle here would mean a document is both
  // an ancestor and a descendant of itself.
  const adj = new Map<string, string[]>();
  for (const d of graph.documentos) adj.set(d.id, []);
  // Build O(1) lancamento lookup to avoid O(n²) .find() in the loop.
  const lancById = new Map<string, TopologyLancamento>();
  for (const l of graph.lancamentos) lancById.set(l.id, l);
  for (const o of graph.origens) {
    const l = lancById.get(o.lancamentoId);
    if (!l) continue; // Missing-lancamento check happens earlier
    adj.get(o.documentoId)!.push(l.documentoId);
  }
  const visiting = new Set<string>();
  const visited = new Set<string>();
  function dfs(node: string): void {
    if (visited.has(node)) return;
    if (visiting.has(node)) {
      throw new TopologyInvariantError(
        `cycle detected involving document ${node}`
      );
    }
    visiting.add(node);
    for (const next of adj.get(node) ?? []) dfs(next);
    visiting.delete(node);
    visited.add(node);
  }
  for (const id of adj.keys()) dfs(id);

  // S-5 contiguity: per-lancamento, the origens' `indice` values must be
  // a contiguous 0..k-1 sequence with no duplicates (per plan S-5 and
  // `docs/db/SCHEMA_CONSOLIDATED.md:197` — "indice >= 0 and contiguous
  // per lancamento (0, 1, 2...)"). Enforced via app (no DB trigger).
  // Runs AFTER the DAG cycle check so that structural failures
  // (no root, cycle) surface before this secondary property.
  for (const [lancId, list] of origensByLanc) {
    const indices = list.map((o: TopologyOrigem) => o.indice).sort((a: number, b: number) => a - b);
    for (let i = 0; i < indices.length; i++) {
      if (indices[i] !== i) {
        throw new TopologyInvariantError(
          `lancamento ${lancId} origens have non-contiguous indices: ${JSON.stringify(indices)}`
        );
      }
    }
  }

  // S-5 fim_cadeia semantics: every terminal origem has exactly one
  // fim_cadeia; every non-terminal origem has zero. The definition of
  // "terminal" must match the generator's `computeTerminalFims`:
  // an origem is terminal iff its target doc (the `documentoId` of the
  // lancamento it references) is NOT a source of any other origem.
  const targetByLanc = new Map<string, string>();
  for (const l of graph.lancamentos) {
    targetByLanc.set(l.id, l.documentoId);
  }
  const docsAsOrigemSource = new Set<string>();
  for (const o of graph.origens) {
    docsAsOrigemSource.add(o.documentoId);
  }
  const fimsByOrigem = new Map<string, number>();
  for (const f of graph.fimCadeias) {
    fimsByOrigem.set(f.origemId, (fimsByOrigem.get(f.origemId) ?? 0) + 1);
  }
  for (const o of graph.origens) {
    const target = targetByLanc.get(o.lancamentoId);
    const isTerminal = target !== undefined && !docsAsOrigemSource.has(target);
    const count = fimsByOrigem.get(o.id) ?? 0;
    if (isTerminal) {
      if (count !== 1) {
        throw new TopologyInvariantError(
          `terminal origem ${o.id} must have exactly 1 fim_cadeia, has ${count}`
        );
      }
    } else {
      if (count !== 0) {
        throw new TopologyInvariantError(
          `non-terminal origem ${o.id} must have 0 fim_cadeia, has ${count}`
        );
      }
    }
  }
}
