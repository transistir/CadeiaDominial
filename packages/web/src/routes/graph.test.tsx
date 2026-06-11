import type { ReactElement, ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import GraphRoute from "./graph";

const fitViewSpy = vi.hoisted(() => vi.fn());

vi.mock("@xyflow/react", () => ({
  ReactFlow: ({
    nodes,
    edges,
    fitView,
    children
  }: {
    nodes: unknown[];
    edges: unknown[];
    fitView?: (() => void) | null;
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
              data?: { label?: string; numero?: string };
            };
            return (
              <div key={n.id} data-node-id={n.id}>
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
        {children}
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

vi.mock("../graph/mock", () => ({
  generateMockGraph: vi.fn((shape: string) => {
    if (shape === "linear") {
      return {
        nodes: [
          { id: "doc-1", label: "Documento M1", type: "documento", data: { numero: "M1", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-01" } },
          { id: "doc-2", label: "Documento M2", type: "documento", data: { numero: "M2", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-02" } },
          { id: "doc-3", label: "Documento M3", type: "documento", data: { numero: "M3", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-03" } },
          { id: "doc-4", label: "Documento M4", type: "documento", data: { numero: "M4", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-04" } },
          { id: "doc-5", label: "Documento M5", type: "documento", data: { numero: "M5", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-05" } },
          { id: "fim-5", label: "Fim de cadeia", type: "fimCadeia", data: { classificacao: "inconclusa" } }
        ],
        edges: [
          { id: "orig-1", source: "doc-1", target: "doc-2", data: { tipoOrigem: "matricula" } },
          { id: "orig-2", source: "doc-2", target: "doc-3", data: { tipoOrigem: "matricula" } },
          { id: "orig-3", source: "doc-3", target: "doc-4", data: { tipoOrigem: "matricula" } },
          { id: "orig-4", source: "doc-4", target: "doc-5", data: { tipoOrigem: "matricula" } },
          { id: "doc-5->fim-5", source: "doc-5", target: "fim-5", data: { tipoOrigem: "fim_cadeia" } }
        ]
      };
    }
    if (shape === "branching") {
      return {
        nodes: [
          { id: "doc-1", label: "Documento M1", type: "documento", data: { numero: "M1", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-01" } },
          { id: "doc-2", label: "Documento M2", type: "documento", data: { numero: "M2", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-02" } },
          { id: "doc-3", label: "Documento T1", type: "documento", data: { numero: "T1", tipo: "transcricao", cartorioId: "cartorio-1", data: "2024-01-03" } },
          { id: "doc-4", label: "Documento M4", type: "documento", data: { numero: "M4", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-04" } },
          { id: "fim-3", label: "Fim de cadeia", type: "fimCadeia", data: { classificacao: "origem_lidima" } },
          { id: "fim-4", label: "Fim de cadeia", type: "fimCadeia", data: { classificacao: "sem_origem" } }
        ],
        edges: [
          { id: "orig-1", source: "doc-1", target: "doc-2", data: { tipoOrigem: "matricula" } },
          { id: "orig-2", source: "doc-2", target: "doc-3", data: { tipoOrigem: "matricula" } },
          { id: "orig-3", source: "doc-2", target: "doc-4", data: { tipoOrigem: "matricula" } },
          { id: "doc-3->fim-3", source: "doc-3", target: "fim-3", data: { tipoOrigem: "fim_cadeia" } },
          { id: "doc-4->fim-4", source: "doc-4", target: "fim-4", data: { tipoOrigem: "fim_cadeia" } }
        ]
      };
    }
    if (shape === "merge") {
      return {
        nodes: [
          { id: "doc-1", label: "Documento M1", type: "documento", data: { numero: "M1", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-01" } },
          { id: "doc-2", label: "Documento T1", type: "documento", data: { numero: "T1", tipo: "transcricao", cartorioId: "cartorio-1", data: "2024-01-02" } },
          { id: "doc-3", label: "Documento M3", type: "documento", data: { numero: "M3", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-03" } },
          { id: "fim-3", label: "Fim de cadeia", type: "fimCadeia", data: { classificacao: "inconclusa" } }
        ],
        edges: [
          { id: "orig-1", source: "doc-1", target: "doc-3", data: { tipoOrigem: "matricula" } },
          { id: "orig-2", source: "doc-2", target: "doc-3", data: { tipoOrigem: "transcricao" } },
          { id: "doc-3->fim-3", source: "doc-3", target: "fim-3", data: { tipoOrigem: "fim_cadeia" } }
        ]
      };
    }
    return {
      nodes: [
        { id: "doc-01", label: "Documento M1", type: "documento", data: { numero: "M1", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-01" } },
        { id: "doc-02", label: "Documento M2", type: "documento", data: { numero: "M2", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-02" } },
        { id: "doc-03", label: "Documento T1", type: "documento", data: { numero: "T1", tipo: "transcricao", cartorioId: "cartorio-1", data: "2024-01-03" } },
        { id: "doc-04", label: "Documento M4", type: "documento", data: { numero: "M4", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-04" } },
        { id: "doc-05", label: "Documento T2", type: "documento", data: { numero: "T2", tipo: "transcricao", cartorioId: "cartorio-1", data: "2024-01-05" } },
        { id: "doc-06", label: "Documento M6", type: "documento", data: { numero: "M6", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-06" } },
        { id: "doc-07", label: "Documento M7", type: "documento", data: { numero: "M7", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-07" } },
        { id: "doc-08", label: "Documento T3", type: "documento", data: { numero: "T3", tipo: "transcricao", cartorioId: "cartorio-1", data: "2024-01-08" } },
        { id: "doc-09", label: "Documento M9", type: "documento", data: { numero: "M9", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-09" } },
        { id: "doc-10", label: "Documento T4", type: "documento", data: { numero: "T4", tipo: "transcricao", cartorioId: "cartorio-1", data: "2024-01-10" } },
        { id: "doc-11", label: "Documento M11", type: "documento", data: { numero: "M11", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-11" } },
        { id: "doc-12", label: "Documento T5", type: "documento", data: { numero: "T5", tipo: "transcricao", cartorioId: "cartorio-1", data: "2024-01-12" } },
        { id: "doc-13", label: "Documento M13", type: "documento", data: { numero: "M13", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-13" } },
        { id: "doc-14", label: "Documento T6", type: "documento", data: { numero: "T6", tipo: "transcricao", cartorioId: "cartorio-1", data: "2024-01-14" } },
        { id: "doc-15", label: "Documento M15", type: "documento", data: { numero: "M15", tipo: "matricula", cartorioId: "cartorio-1", data: "2024-01-15" } },
        { id: "doc-16", label: "Documento T7", type: "documento", data: { numero: "T7", tipo: "transcricao", cartorioId: "cartorio-1", data: "2024-01-16" } },
        { id: "fim-11", label: "Fim de cadeia", type: "fimCadeia", data: { classificacao: "inconclusa" } },
        { id: "fim-12", label: "Fim de cadeia", type: "fimCadeia", data: { classificacao: "origem_lidima" } },
        { id: "fim-13", label: "Fim de cadeia", type: "fimCadeia", data: { classificacao: "sem_origem" } },
        { id: "fim-14", label: "Fim de cadeia", type: "fimCadeia", data: { classificacao: "inconclusa" } },
        { id: "fim-16", label: "Fim de cadeia", type: "fimCadeia", data: { classificacao: "sem_origem" } }
      ],
      edges: [
        { id: "orig-1", source: "doc-01", target: "doc-02", data: { tipoOrigem: "matricula" } },
        { id: "orig-2", source: "doc-02", target: "doc-03", data: { tipoOrigem: "matricula" } },
        { id: "orig-3", source: "doc-03", target: "doc-04", data: { tipoOrigem: "transcricao" } },
        { id: "orig-4", source: "doc-04", target: "doc-05", data: { tipoOrigem: "matricula" } },
        { id: "orig-5", source: "doc-05", target: "doc-06", data: { tipoOrigem: "transcricao" } },
        { id: "orig-6", source: "doc-06", target: "doc-07", data: { tipoOrigem: "matricula" } },
        { id: "orig-7", source: "doc-07", target: "doc-08", data: { tipoOrigem: "matricula" } },
        { id: "orig-8", source: "doc-08", target: "doc-09", data: { tipoOrigem: "transcricao" } },
        { id: "orig-9", source: "doc-09", target: "doc-10", data: { tipoOrigem: "matricula" } },
        { id: "orig-10", source: "doc-10", target: "doc-11", data: { tipoOrigem: "transcricao" } },
        { id: "doc-11->fim-11", source: "doc-11", target: "fim-11", data: { tipoOrigem: "fim_cadeia" } },
        { id: "orig-12", source: "doc-03", target: "doc-12", data: { tipoOrigem: "transcricao" } },
        { id: "doc-12->fim-12", source: "doc-12", target: "fim-12", data: { tipoOrigem: "fim_cadeia" } },
        { id: "orig-13", source: "doc-05", target: "doc-13", data: { tipoOrigem: "transcricao" } },
        { id: "doc-13->fim-13", source: "doc-13", target: "fim-13", data: { tipoOrigem: "fim_cadeia" } },
        { id: "orig-14", source: "doc-07", target: "doc-14", data: { tipoOrigem: "matricula" } },
        { id: "doc-14->fim-14", source: "doc-14", target: "fim-14", data: { tipoOrigem: "fim_cadeia" } },
        { id: "orig-15", source: "doc-09", target: "doc-15", data: { tipoOrigem: "matricula" } },
        { id: "orig-16", source: "doc-15", target: "doc-16", data: { tipoOrigem: "matricula" } },
        { id: "doc-16->fim-16", source: "doc-16", target: "fim-16", data: { tipoOrigem: "fim_cadeia" } }
      ]
    };
  })
}));

describe("GraphRoute", () => {
  const originalGetBoundingClientRect = HTMLElement.prototype.getBoundingClientRect;
  const originalClientWidth = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "clientWidth");
  const originalClientHeight = Object.getOwnPropertyDescriptor(
    HTMLElement.prototype,
    "clientHeight"
  );

  beforeEach(() => {
    fitViewSpy.mockClear();

    Object.defineProperty(HTMLElement.prototype, "clientWidth", {
      configurable: true,
      get: () => 840
    });
    Object.defineProperty(HTMLElement.prototype, "clientHeight", {
      configurable: true,
      get: () => 420
    });
    HTMLElement.prototype.getBoundingClientRect = () => ({
      width: 840,
      height: 420,
      top: 0,
      left: 0,
      right: 840,
      bottom: 420,
      x: 0,
      y: 0,
      toJSON: () => {}
    });
  });

  afterEach(() => {
    fitViewSpy.mockClear();
    vi.restoreAllMocks();

    if (originalClientWidth) {
      Object.defineProperty(HTMLElement.prototype, "clientWidth", originalClientWidth);
    } else {
      Object.defineProperty(HTMLElement.prototype, "clientWidth", {
        configurable: true,
        get: () => 0
      });
    }
    if (originalClientHeight) {
      Object.defineProperty(HTMLElement.prototype, "clientHeight", originalClientHeight);
    } else {
      Object.defineProperty(HTMLElement.prototype, "clientHeight", {
        configurable: true,
        get: () => 0
      });
    }
    HTMLElement.prototype.getBoundingClientRect = originalGetBoundingClientRect;
  });

  it("renders graph view with complex mock by default", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});

    render(<GraphRoute />);

    const graphView = screen.getByTestId("graph-view");
    expect(graphView).toBeInTheDocument();

    expect(screen.getByTestId("mock-shape-select")).toBeInTheDocument();
    expect(screen.getByText("Complexo")).toBeInTheDocument();

    expect(screen.getByText("M1")).toBeInTheDocument();
    expect(screen.getByText("T1")).toBeInTheDocument();
    expect(screen.getAllByText("Fim de cadeia")).toHaveLength(5);

    expect(screen.getByTestId("reactflow-controls")).toBeInTheDocument();
    expect(screen.getByTestId("reactflow-minimap")).toBeInTheDocument();

    expect(fitViewSpy).toHaveBeenCalled();
    expect(consoleError).not.toHaveBeenCalled();
  });

  it("renders mock shape selector with 4 options", () => {
    render(<GraphRoute />);

    const select = screen.getByTestId("mock-shape-select");
    expect(select).toBeInTheDocument();

    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(4);
    expect(options[0]).toHaveTextContent("Linear");
    expect(options[1]).toHaveTextContent("Branching");
    expect(options[2]).toHaveTextContent("Merge");
    expect(options[3]).toHaveTextContent("Complexo");
  });

  it("switching shape re-renders graph view", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});

    render(<GraphRoute />);

    expect(screen.getByText("M1")).toBeInTheDocument();
    expect(screen.getByText("T1")).toBeInTheDocument();

    const select = screen.getByTestId("mock-shape-select");
    select.click();

    const linearOption = screen.getByRole("option", { name: "Linear" });
    linearOption.click();

    expect(consoleError).not.toHaveBeenCalled();
  });
});
