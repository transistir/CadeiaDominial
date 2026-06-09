import dagre from "@dagrejs/dagre";
import type { GraphJson } from "./types";

/**
 * Layout result: every input node is annotated with a 2D position produced by
 * a deterministic dagre LR (left-to-right) layout. The edges pass through
 * unchanged.
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
const NODE_HEIGHT = 40;

/**
 * Run a deterministic left-to-right dagre layout over a `GraphJson`.
 *
 * **Contract:** the caller must have already run `validateGraph` on the
 * input. This function trusts that `graph.nodes` and `graph.edges` are
 * well-formed arrays, every edge references a known node, and IDs are unique.
 * It does NOT re-validate; that work belongs at the trust boundary (loader,
 * network, file), and `validateGraph` is that boundary.
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

  // Extract positioned nodes
  const layoutedNodes: LayoutedNode[] = graph.nodes.map((node) => {
    const pos = dagreGraph.node(node.id);
    return {
      id: node.id,
      label: node.label,
      type: node.type,
      position: {
        x: pos.x - NODE_WIDTH / 2,
        y: pos.y - NODE_HEIGHT / 2
      },
      data: node.data
    };
  });

  return {
    nodes: layoutedNodes,
    edges: graph.edges
  };
}
