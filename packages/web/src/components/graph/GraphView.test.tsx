import React, { type ReactElement, type ReactNode } from "react";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { GraphView } from "./GraphView";

const fitViewSpy = vi.hoisted(() => vi.fn());

vi.mock("@xyflow/react", () => ({
  ReactFlow: ({
    nodes,
    edges,
    fitView,
    onNodeClick,
    onPaneClick,
    children
  }: {
    nodes: unknown[];
    edges: unknown[];
    fitView?: (() => void) | null;
    onNodeClick?: (_event: React.MouseEvent, node: unknown) => void;
    onPaneClick?: () => void;
    children?: ReactNode;
  }): ReactElement => {
    if (fitView) {
      fitViewSpy();
    }

    return (
      <div data-testid="reactflow">
        <div data-testid="nodes">
          {nodes.map((node: unknown) => {
            const n = node as {
              id: string;
              type?: string;
              data?: { label?: string; numero?: string; classificacao?: string };
            };
            return (
              <div 
                key={n.id} 
                data-node-id={n.id}
                data-node-type={n.type}
                onClick={(e) => onNodeClick?.(e, n)}
              >
                {n.data?.numero ??
                  n.data?.label ??
                  (n.type === "fimCadeia" ? "Fim de cadeia" : n.id)}
              </div>
            );
          })}
        </div>
        <div data-testid="edges">
          {edges.map((edge: unknown) => {
            const e = edge as { id: string };
            return (
              <div key={e.id} data-edge-id={e.id}>
                {e.id}
              </div>
            );
          })}
        </div>
        <div 
          data-testid="reactflow-pane" 
          onClick={onPaneClick}
          style={{ width: '100%', height: '100%' }}
        >
          {children}
        </div>
      </div>
    );
  },
  ReactFlowProvider: ({ children }: { children: ReactNode }): ReactElement => (
    <div data-testid="reactflow-provider">{children}</div>
  ),
  Background: () => <div data-testid="reactflow-background" />,
  Controls: () => <div data-testid="reactflow-controls" />,
  MiniMap: () => <div data-testid="reactflow-minimap" />
}));

vi.mock("./DocumentoNode", () => ({
  DocumentoNode: ({ data }: { data: { numero: string } }) => (
    <div data-testid="documento-node">{data.numero}</div>
  )
}));

vi.mock("./FimCadeiaNode", () => ({
  FimCadeiaNode: ({ data }: { data: { classificacao: string } }) => (
    <div data-testid="fim-cadeia-node">{data.classificacao}</div>
  )
}));

vi.mock("./OrigemEdge", () => ({
  OrigemEdge: () => <div data-testid="origem-edge" />
}));

const mockGraph = {
  nodes: [
    { id: "doc-1", label: "Documento M1", type: "documento", data: { numero: "M1", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-01" } },
    { id: "doc-2", label: "Documento M2", type: "documento", data: { numero: "M2", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-02" } },
    { id: "fim-1", label: "Fim de cadeia", type: "fimCadeia", data: { classificacao: "inconclusa" } }
  ],
  edges: [
    { id: "orig-1", source: "doc-1", target: "doc-2", data: { tipoOrigem: "matricula" } },
    { id: "doc-2->fim-1", source: "doc-2", target: "fim-1", data: { tipoOrigem: "fim_cadeia" } }
  ]
};

describe("GraphView", () => {
  beforeEach(() => {
    fitViewSpy.mockClear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders with valid graph data", () => {
    render(<GraphView graph={mockGraph} />);

    const graphView = screen.getByTestId("graph-view");
    expect(graphView).toBeInTheDocument();

    expect(screen.getByTestId("reactflow")).toBeInTheDocument();
    expect(screen.getByTestId("reactflow-controls")).toBeInTheDocument();
    expect(screen.getByTestId("reactflow-minimap")).toBeInTheDocument();
    expect(fitViewSpy).toHaveBeenCalled();
  });

  it("renders detail panel in closed state by default", () => {
    render(<GraphView graph={mockGraph} />);

    const detailPanel = screen.getByTestId("detail-panel");
    expect(detailPanel).toBeInTheDocument();
    expect(detailPanel).toHaveClass("graph-view__panel--closed");
    expect(detailPanel).not.toHaveClass("graph-view__panel--open");
    expect(detailPanel).toHaveAttribute("aria-hidden", "true");
    expect(detailPanel).toHaveAttribute("aria-label", "Detalhes do nó");
    expect(screen.getByTestId("detail-panel-close")).toHaveAttribute("tabindex", "-1");
  });

  it("opens detail panel when node is clicked", () => {
    render(<GraphView graph={mockGraph} />);

    const detailPanel = screen.getByTestId("detail-panel");
    expect(detailPanel).toHaveClass("graph-view__panel--closed");

    const docNode = screen.getByTestId("nodes").querySelector('[data-node-id="doc-1"]');
    expect(docNode).toBeInTheDocument();
    
    if (docNode) {
      fireEvent.click(docNode);
      
      expect(detailPanel).toHaveClass("graph-view__panel--open");
      expect(detailPanel).not.toHaveClass("graph-view__panel--closed");
      expect(detailPanel).toHaveAttribute("aria-hidden", "false");
      expect(screen.getByTestId("detail-panel-close")).not.toHaveAttribute("tabindex");
    }
  });

  it("closes detail panel when pane is clicked", () => {
    render(<GraphView graph={mockGraph} />);

    const detailPanel = screen.getByTestId("detail-panel");
    
    // First open the panel
    const docNode = screen.getByTestId("nodes").querySelector('[data-node-id="doc-1"]');
    expect(docNode).toBeInTheDocument();
    
    if (docNode) {
      fireEvent.click(docNode);
      expect(detailPanel).toHaveClass("graph-view__panel--open");
      
      // Now close it by clicking the pane
      const pane = screen.getByTestId("reactflow-pane");
      fireEvent.click(pane);
      
      expect(detailPanel).toHaveClass("graph-view__panel--closed");
      expect(detailPanel).not.toHaveClass("graph-view__panel--open");
    }
  });

  it("closes detail panel when close button is clicked", () => {
    render(<GraphView graph={mockGraph} />);

    const detailPanel = screen.getByTestId("detail-panel");
    
    // First open the panel
    const docNode = screen.getByTestId("nodes").querySelector('[data-node-id="doc-1"]');
    expect(docNode).toBeInTheDocument();
    
    if (docNode) {
      fireEvent.click(docNode);
      expect(detailPanel).toHaveClass("graph-view__panel--open");
      
      // Now close it by clicking the close button
      const closeButton = screen.getByTestId("detail-panel-close");
      fireEvent.click(closeButton);
      
      expect(detailPanel).toHaveClass("graph-view__panel--closed");
      expect(detailPanel).not.toHaveClass("graph-view__panel--open");
    }
  });

  it("shows correct node data for documento nodes", () => {
    render(<GraphView graph={mockGraph} />);

    const docNode = screen.getByTestId("nodes").querySelector('[data-node-id="doc-1"]');
    expect(docNode).toBeInTheDocument();

    if (docNode) {
      fireEvent.click(docNode);

      const detailPanel = screen.getByTestId("detail-panel");
      const panelBody = within(detailPanel);

      expect(panelBody.getByText("Número")).toBeInTheDocument();
      expect(panelBody.getByText("M1")).toBeInTheDocument();
      expect(panelBody.getByText("Tipo")).toBeInTheDocument();
      expect(panelBody.getByText("matricula")).toBeInTheDocument();
      expect(panelBody.getByText("Cartório")).toBeInTheDocument();
      expect(panelBody.getByText("cartorio-1")).toBeInTheDocument();
      expect(panelBody.getByText("Data")).toBeInTheDocument();
      expect(panelBody.getByText("2024-01-01")).toBeInTheDocument();
    }
  });

  it("shows classificacao for fimCadeia nodes", () => {
    render(<GraphView graph={mockGraph} />);

    const fimNode = screen.getByTestId("nodes").querySelector('[data-node-id="fim-1"]');
    expect(fimNode).toBeInTheDocument();

    if (fimNode) {
      fireEvent.click(fimNode);

      const detailPanel = screen.getByTestId("detail-panel");
      const panelBody = within(detailPanel);

      expect(panelBody.getByText("Classificação")).toBeInTheDocument();
      expect(panelBody.getByText("inconclusa")).toBeInTheDocument();
    }
  });
});
