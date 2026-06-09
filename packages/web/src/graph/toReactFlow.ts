import type { Node, Edge } from "@xyflow/react";
import type { LayoutedGraph } from "./layoutGraph";

export function toReactFlow(graph: LayoutedGraph): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = graph.nodes.map((node) => ({
    id: node.id,
    type: "default",
    position: node.position,
    data: { label: node.label },
    draggable: false,
  }));

  const edges: Edge[] = graph.edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    type: "smoothstep",
    animated: false,
  }));

  return { nodes, edges };
}
