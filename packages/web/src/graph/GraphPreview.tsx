import { useMemo } from "react";
import { ReactFlow, ReactFlowProvider, Background } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { GraphJson } from "./types";
import { validateGraph } from "./validateGraph";
import { layoutGraph } from "./layoutGraph";
import { toReactFlow } from "./toReactFlow";

export function GraphPreview({ graph }: { graph: GraphJson }) {
  const { nodes, edges } = useMemo(() => {
    validateGraph(graph);
    const layouted = layoutGraph(graph);
    return toReactFlow(layouted);
  }, [graph]);

  return (
    <div data-testid="graph-preview" style={{ width: "100vw", height: "100vh" }}>
      <ReactFlowProvider>
        <ReactFlow
          nodes={nodes}
          edges={edges}
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
