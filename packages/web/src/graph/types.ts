export interface GraphNode {
  id: string;
  label: string;
  type: string;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
}

export interface GraphJson {
  nodes: GraphNode[];
  edges: GraphEdge[];
}
