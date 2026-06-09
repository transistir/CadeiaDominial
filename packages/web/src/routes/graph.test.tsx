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
  Background: () => <div data-testid="reactflow-background" />
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

  it("mounts the graph preview and renders nodes, edges, and fitView", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});

    render(<GraphRoute />);

    const graphPreview = screen.getByTestId("graph-preview");
    expect(graphPreview).toBeInTheDocument();

    expect(screen.getByText("M1234")).toBeInTheDocument();
    expect(screen.getByText("T5678")).toBeInTheDocument();
    expect(screen.getByText("Fim de cadeia")).toBeInTheDocument();
    expect(fitViewSpy).toHaveBeenCalled();
    expect(consoleError).not.toHaveBeenCalled();
  });
});
