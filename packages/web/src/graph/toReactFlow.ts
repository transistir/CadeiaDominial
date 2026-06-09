import type { Node, Edge } from "@xyflow/react";
import type { LayoutedGraph } from "./layoutGraph";

export function toReactFlow(graph: LayoutedGraph): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = graph.nodes.map((node) => ({
    id: node.id,
    type: node.type,
    position: node.position,
    data: toNodeData(node.data, node.label),
    draggable: false
  }));

  const edges: Edge[] = graph.edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    type: edge.data?.tipoOrigem ? "origem" : "smoothstep",
    animated: false,
    data: edge.data
  }));

  return { nodes, edges };
}

function toNodeData(data: unknown, label: string): Record<string, unknown> {
  if (data !== null && typeof data === "object" && !Array.isArray(data)) {
    return data as Record<string, unknown>;
  }
  return { label };
}
