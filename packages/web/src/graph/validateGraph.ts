import type { GraphJson } from "./types";

export function validateGraph(graph: GraphJson): void {
  // Check unique node IDs
  const nodeIds = new Set<string>();
  for (const node of graph.nodes) {
    if (nodeIds.has(node.id)) {
      throw new Error(`Duplicate node ID: ${node.id}`);
    }
    nodeIds.add(node.id);
  }

  // Check unique edge IDs
  const edgeIds = new Set<string>();
  for (const edge of graph.edges) {
    if (edgeIds.has(edge.id)) {
      throw new Error(`Duplicate edge ID: ${edge.id}`);
    }
    edgeIds.add(edge.id);

    // Check edge references valid nodes
    if (!nodeIds.has(edge.source)) {
      throw new Error(`Edge ${edge.id} references non-existent source: ${edge.source}`);
    }
    if (!nodeIds.has(edge.target)) {
      throw new Error(`Edge ${edge.id} references non-existent target: ${edge.target}`);
    }
  }
}
