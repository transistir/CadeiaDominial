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
const VERTICAL_GAP = 20;

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
  // Dagre determines horizontal ranks but doesn't guarantee vertical order.
  // Group nodes by X (rounded to 10px), sort each group by vertical priority
  // (matrículas↑, transcrições↓), and reassign Y positions.
  const X_TOLERANCE = 10;
  const rankGroups = new Map<number, { id: string; dagreY: number }[]>();

  for (const node of graph.nodes) {
    const dagrePos = dagreGraph.node(node.id);
    const rankX = Math.round(dagrePos.x / X_TOLERANCE) * X_TOLERANCE;
    if (!rankGroups.has(rankX)) rankGroups.set(rankX, []);
    rankGroups.get(rankX)!.push({ id: node.id, dagreY: dagrePos.y });
  }

  // Sort each rank by vertical priority, then assign Y from top to bottom
  const nodeY = new Map<string, number>();
  for (const [, group] of rankGroups) {
    group.sort((a, b) => {
      const nodeA = graph.nodes.find((n) => n.id === a.id)!;
      const nodeB = graph.nodes.find((n) => n.id === b.id)!;
      return verticalPriority(nodeA) - verticalPriority(nodeB);
    });

    let y = 0;
    for (const item of group) {
      nodeY.set(item.id, y);
      y += NODE_HEIGHT + VERTICAL_GAP;
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
