import dagre from "@dagrejs/dagre";
import type { GraphJson } from "./types";

export interface LayoutedNode {
  id: string;
  label: string;
  type: string;
  position: { x: number; y: number };
}

export interface LayoutedGraph {
  nodes: LayoutedNode[];
  edges: GraphJson["edges"];
}

const NODE_WIDTH = 180;
const NODE_HEIGHT = 40;

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
        y: pos.y - NODE_HEIGHT / 2,
      },
    };
  });

  return {
    nodes: layoutedNodes,
    edges: graph.edges,
  };
}
