import type { GraphJson, GraphNode, GraphEdge } from "./types";

/**
 * Validate a graph JSON payload from an untrusted source (loader, network, file).
 * Returns a strongly-typed GraphJson so downstream code never has to re-narrow.
 *
 * Throws on:
 * - non-object payloads
 * - missing or non-array `nodes` / `edges`
 * - nodes / edges missing required string fields
 * - duplicate node or edge IDs
 * - edge endpoints that don't reference an existing node
 */
export function validateGraph(input: unknown): GraphJson {
  if (input === null || typeof input !== "object") {
    throw new Error("Graph must be an object");
  }
  const obj = input as Record<string, unknown>;

  if (!Array.isArray(obj.nodes)) {
    throw new Error("Graph.nodes must be an array");
  }
  if (!Array.isArray(obj.edges)) {
    throw new Error("Graph.edges must be an array");
  }

  const nodes: GraphNode[] = [];
  for (const [i, raw] of obj.nodes.entries()) {
    if (raw === null || typeof raw !== "object") {
      throw new Error(`nodes[${i}] must be an object`);
    }
    const n = raw as Record<string, unknown>;
    if (typeof n.id !== "string" || n.id.length === 0) {
      throw new Error(`nodes[${i}].id must be a non-empty string`);
    }
    if (typeof n.label !== "string") {
      throw new Error(`nodes[${i}].label must be a string`);
    }
    if (typeof n.type !== "string") {
      throw new Error(`nodes[${i}].type must be a string`);
    }
    nodes.push({ id: n.id, label: n.label, type: n.type });
  }

  const edges: GraphEdge[] = [];
  for (const [i, raw] of obj.edges.entries()) {
    if (raw === null || typeof raw !== "object") {
      throw new Error(`edges[${i}] must be an object`);
    }
    const e = raw as Record<string, unknown>;
    if (typeof e.id !== "string" || e.id.length === 0) {
      throw new Error(`edges[${i}].id must be a non-empty string`);
    }
    if (typeof e.source !== "string" || e.source.length === 0) {
      throw new Error(`edges[${i}].source must be a non-empty string`);
    }
    if (typeof e.target !== "string" || e.target.length === 0) {
      throw new Error(`edges[${i}].target must be a non-empty string`);
    }
    edges.push({ id: e.id, source: e.source, target: e.target });
  }

  // Integrity: unique node IDs
  const nodeIds = new Set<string>();
  for (const node of nodes) {
    if (nodeIds.has(node.id)) {
      throw new Error(`Duplicate node ID: ${node.id}`);
    }
    nodeIds.add(node.id);
  }

  // Integrity: unique edge IDs and valid endpoint references
  const edgeIds = new Set<string>();
  for (const edge of edges) {
    if (edgeIds.has(edge.id)) {
      throw new Error(`Duplicate edge ID: ${edge.id}`);
    }
    edgeIds.add(edge.id);

    if (!nodeIds.has(edge.source)) {
      throw new Error(`Edge ${edge.id} references non-existent source: ${edge.source}`);
    }
    if (!nodeIds.has(edge.target)) {
      throw new Error(`Edge ${edge.id} references non-existent target: ${edge.target}`);
    }
  }

  return { nodes, edges };
}
