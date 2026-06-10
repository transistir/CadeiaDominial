import { useMemo } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  type EdgeTypes,
  type NodeTypes
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { validateGraph } from "./validateGraph";
import { layoutGraph } from "./layoutGraph";
import { toReactFlow } from "./toReactFlow";
import { DocumentoNode } from "../components/graph/DocumentoNode";
import { FimCadeiaNode } from "../components/graph/FimCadeiaNode";
import { OrigemEdge } from "../components/graph/OrigemEdge";

const nodeTypes: NodeTypes = {
  documento: DocumentoNode,
  fimCadeia: FimCadeiaNode
};

const edgeTypes: EdgeTypes = {
  origem: OrigemEdge
};

export function GraphPreview({ graph }: { graph: unknown }) {
  const { nodes, edges } = useMemo(() => {
    const validated = validateGraph(graph);
    const layouted = layoutGraph(validated);
    return toReactFlow(layouted);
  }, [graph]);

  return (
    <div data-testid="graph-preview" style={{ width: "100vw", height: "100vh" }}>
      <ReactFlowProvider>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          defaultEdgeOptions={{ animated: false }}
        >
          <Background />
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  );
}
