import dagre from "@dagrejs/dagre";
import type { GraphJson, DocumentoData } from "./types";

/**
 * Layout result: every input node is annotated with a 2D position produced by
 * a deterministic dagre LR (left-to-right) layout, then vertically reordered
 * within each rank so matrículas (higher número) appear above transcrições.
 * The edges pass through unchanged.
 */
export interface LayoutedNode {
  id: string;
  label: string;
  type: string;
  position: { x: number; y: number };
  data?: unknown;
}

export interface LayoutedGraph {
  nodes: LayoutedNode[];
  edges: GraphJson["edges"];
}

const NODE_WIDTH = 180;
const NODE_HEIGHT = 80;

/**
 * Extract a sortable priority for vertical ordering within a dagre rank.
 *
 * Lower priority = higher on screen.
 * Matrículas occupy 0–999, transcrições 1000–1999, fim-cadeia 9999.
 * Within each type, higher número → lower priority (appears first).
 */
function verticalPriority(node: GraphJson["nodes"][number]): number {
  if (node.type === "fimCadeia") return Number.MAX_SAFE_INTEGER;
  if (node.type !== "documento") return Number.MAX_SAFE_INTEGER - 1;

  const data = node.data as DocumentoData | undefined;
  const raw = data?.numero?.replace(/\D/g, "") ?? "0";
  const num = Number.parseInt(raw, 10) || 0;

  // Matrículas get negative priority → sort above transcrições.
  // Larger número → more negative → appears first (top of screen).
  // Transcrições get positive offset, also sorted by número descending.
  return data?.tipo === "matricula" ? -num : 1_000_000 - num;
}

/**
 * Run a deterministic left-to-right dagre layout, then reorder nodes
 * vertically within each rank so matrículas (bigger número) sit above
 * transcrições, and fim-de-cadeia nodes sit at the bottom.
 */
export function layoutGraph(graph: GraphJson): LayoutedGraph {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({ rankdir: "LR", ranksep: 80, nodesep: 40 });

  // Add nodes
  for (const node of graph.nodes) {
    dagreGraph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }

  // Add edges
  for (const edge of graph.edges) {
    dagreGraph.setEdge(edge.source, edge.target);
  }

  // Run layout
  dagre.layout(dagreGraph);

  // ── Vertical reorder within each rank ──────────────────────────────────
  // Dagre picks Y positions that minimize edge crossings; that set of Y
  // values is preserved.  We only reassign which node gets which Y inside
  // each horizontal rank.  Group by coarse X (rankstep ≈ 260px) so nodes
  // in the same visual column land in the same sort group.
  const rankNodes = new Map<number, string[]>();

  for (const node of graph.nodes) {
    const pos = dagreGraph.node(node.id);
    // Dagre places nodes at whole-pixel X within each rank — use exact X
    // so nodes in different columns never merge into the same sort group.
    const rank = Math.round(pos.x);
    if (!rankNodes.has(rank)) rankNodes.set(rank, []);
    rankNodes.get(rank)!.push(node.id);
  }

  const nodeY = new Map<string, number>();
  for (const [, ids] of rankNodes) {
    // Collect the Ys dagre assigned to these nodes, sorted ascending.
    const ys = ids
      .map((id) => dagreGraph.node(id).y)
      .sort((a, b) => a - b);

    // Sort node ids by vertical priority (highest priority = smallest Y).
    const sorted = [...ids].sort((a, b) => {
      const nodeA = graph.nodes.find((n) => n.id === a)!;
      const nodeB = graph.nodes.find((n) => n.id === b)!;
      return verticalPriority(nodeA) - verticalPriority(nodeB);
    });

    // Assign the preserved Y values in priority order.
    for (let i = 0; i < sorted.length; i++) {
      nodeY.set(sorted[i], ys[i]);
    }
  }

  // Extract positioned nodes
  const layoutedNodes: LayoutedNode[] = graph.nodes.map((node) => {
    const pos = dagreGraph.node(node.id);
    return {
      id: node.id,
      label: node.label,
      type: node.type,
      position: {
        x: pos.x - NODE_WIDTH / 2,
        y: (nodeY.get(node.id) ?? pos.y) - NODE_HEIGHT / 2,
      },
      data: node.data,
    };
  });

  return {
    nodes: layoutedNodes,
    edges: graph.edges
  };
}
