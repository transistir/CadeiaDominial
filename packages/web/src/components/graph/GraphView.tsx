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

const defaultEdgeOptions = { animated: false };

export function GraphView({ graph }: { graph: unknown }) {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const { nodes, edges } = useMemo(() => {
    const validated = validateGraph(graph);
    const layouted = layoutGraph(validated);
    return toReactFlow(layouted);
  }, [graph]);

  const selectedNode = useMemo(
    () => nodes.find((node) => node.id === selectedNodeId),
    [nodes, selectedNodeId]
  );

  const flowKey = useMemo(
    () =>
      `${nodes.map((node) => node.id).join("|")}::${edges
        .map((edge) => edge.id)
        .join("|")}`,
    [edges, nodes]
  );

  const handleNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    setSelectedNodeId(node.id);
  }, []);

  const handlePaneClick = useCallback(() => {
    setSelectedNodeId(null);
  }, []);

  const handleClosePanel = useCallback(() => {
    setSelectedNodeId(null);
  }, []);

  const panelClass = selectedNode
    ? "graph-view__panel graph-view__panel--open"
    : "graph-view__panel graph-view__panel--closed";

  return (
    <div className="graph-view" data-testid="graph-view">
      <div className="graph-view__flow">
        <ReactFlowProvider>
          <ReactFlow
            key={flowKey}
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            fitView
            nodesDraggable={false}
            nodesConnectable={false}
            onNodeClick={handleNodeClick}
            onPaneClick={handlePaneClick}
            defaultEdgeOptions={defaultEdgeOptions}
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
        aria-hidden={!selectedNode}
        aria-label="Detalhes do nó"
      >
        <header className="graph-view__panel-header">
          <h2>Detalhes</h2>
          <button
            onClick={handleClosePanel}
            className="graph-view__panel-close"
            data-testid="detail-panel-close"
            type="button"
            aria-label="Fechar"
            tabIndex={selectedNode ? undefined : -1}
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
