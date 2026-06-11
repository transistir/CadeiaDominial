import React, { useState, useMemo, useCallback } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  type Node,
  type EdgeTypes,
  type NodeTypes
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { validateGraph } from "../../graph/validateGraph";
import { layoutGraph } from "../../graph/layoutGraph";
import { toReactFlow } from "../../graph/toReactFlow";
import { DocumentoNode } from "./DocumentoNode";
import { FimCadeiaNode } from "./FimCadeiaNode";
import { OrigemEdge } from "./OrigemEdge";
import "./GraphView.css";

const nodeTypes: NodeTypes = {
  documento: DocumentoNode,
  fimCadeia: FimCadeiaNode
};

const edgeTypes: EdgeTypes = {
  origem: OrigemEdge
};

export function GraphView({ graph }: { graph: unknown }) {
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);

  const { nodes, edges } = useMemo(() => {
    const validated = validateGraph(graph);
    const layouted = layoutGraph(validated);
    return toReactFlow(layouted);
  }, [graph]);

  const handleNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    setSelectedNode(node);
  }, []);

  const handlePaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  const handleClosePanel = useCallback(() => {
    setSelectedNode(null);
  }, []);

  const panelClass = selectedNode
    ? "graph-view__panel graph-view__panel--open"
    : "graph-view__panel graph-view__panel--closed";

  return (
    <div className="graph-view" data-testid="graph-view">
      <div className="graph-view__flow">
        <ReactFlowProvider>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            fitView
            nodesDraggable={false}
            nodesConnectable={false}
            onNodeClick={handleNodeClick}
            onPaneClick={handlePaneClick}
            defaultEdgeOptions={{ animated: false }}
          >
            <Background />
            <Controls />
            <MiniMap />
          </ReactFlow>
        </ReactFlowProvider>
      </div>

      <aside
        className={panelClass}
        data-testid="detail-panel"
      >
        <header className="graph-view__panel-header">
          <h2>Detalhes</h2>
          <button
            onClick={handleClosePanel}
            className="graph-view__panel-close"
            data-testid="detail-panel-close"
            type="button"
          >
            ×
          </button>
        </header>
        <div className="graph-view__panel-body">
          {selectedNode ? (
            selectedNode.type === "documento" ? (
              <>
                {"numero" in selectedNode.data && (
                  <div className="graph-view__panel-field">
                    <span className="graph-view__panel-label">Número</span>
                    <span className="graph-view__panel-value">
                      {String(selectedNode.data.numero)}
                    </span>
                  </div>
                )}
                {"tipo" in selectedNode.data && (
                  <div className="graph-view__panel-field">
                    <span className="graph-view__panel-label">Tipo</span>
                    <span className="graph-view__panel-value">
                      {String(selectedNode.data.tipo)}
                    </span>
                  </div>
                )}
                {"cartorioId" in selectedNode.data && (
                  <div className="graph-view__panel-field">
                    <span className="graph-view__panel-label">Cartório</span>
                    <span className="graph-view__panel-value">
                      {String(selectedNode.data.cartorioId)}
                    </span>
                  </div>
                )}
                {"data" in selectedNode.data && typeof selectedNode.data.data === "string" && (
                  <div className="graph-view__panel-field">
                    <span className="graph-view__panel-label">Data</span>
                    <span className="graph-view__panel-value">
                      {String(selectedNode.data.data)}
                    </span>
                  </div>
                )}
              </>
            ) : selectedNode.type === "fimCadeia" ? (
              <>
                {"classificacao" in selectedNode.data && (
                  <div className="graph-view__panel-field">
                    <span className="graph-view__panel-label">Classificação</span>
                    <span className="graph-view__panel-value">
                      {String(selectedNode.data.classificacao)}
                    </span>
                  </div>
                )}
              </>
            ) : null
          ) : null}
        </div>
      </aside>
    </div>
  );
}
