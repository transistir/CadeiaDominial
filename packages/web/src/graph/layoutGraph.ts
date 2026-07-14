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
 * Priority (lower = higher on screen):
 *   0–999     matrículas, sorted by número descending
 *   1000–1999 transcrições, sorted by número descending
 *   2000+     fim-de-cadeia / other
 */
function verticalPriority(node: GraphJson["nodes"][number]): number {
  if (node.type === "fimCadeia") return 9999;
  if (node.type !== "documento") return 9000;

  const data = node.data as DocumentoData | undefined;
  const numero = data?.numero ? Number.parseInt(data.numero.replace(/\D/g, ""), 10) || 0 : 0;

  if (data?.tipo === "matricula") {
    // Higher número first → lower priority value
    return 999 - Math.min(numero, 999);
  }
  // transcricao or averbacao: below matrículas
  return 1999 - Math.min(numero, 999);
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
  // each horizontal rank, so the horizontal layout stays identical.
  const rankNodes = new Map<number, string[]>();

  for (const node of graph.nodes) {
    const dagrePos = dagreGraph.node(node.id);
    const rank = Math.round(dagrePos.x);
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
