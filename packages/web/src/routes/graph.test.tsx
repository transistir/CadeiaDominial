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
            const n = node as { id: string; data?: { label?: string } };
            return (
              <div key={n.id} data-node-id={n.id}>
                {n.data?.label ?? n.id}
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
  Background: () => <div data-testid="reactflow-background" />,
  Controls: () => <div data-testid="reactflow-controls" />
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
      // Restore default JSDOM-like behavior
      Object.defineProperty(HTMLElement.prototype, "clientWidth", {
        configurable: true,
        get: () => 0
      });
    }
    if (originalClientHeight) {
      Object.defineProperty(HTMLElement.prototype, "clientHeight", originalClientHeight);
    } else {
      // Restore default JSDOM-like behavior
      Object.defineProperty(HTMLElement.prototype, "clientHeight", {
        configurable: true,
        get: () => 0
      });
    }
    HTMLElement.prototype.getBoundingClientRect = originalGetBoundingClientRect;
  });

  it("mounts the graph and renders nodes, edges, and fitView", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});

    const { container } = render(<GraphRoute />);

    const graphShell = container.querySelector(".graph-shell") as HTMLElement | null;
    expect(graphShell).not.toBeNull();

    if (!graphShell) {
      throw new Error("Graph shell not found");
    }

    const rect = graphShell.getBoundingClientRect();
    expect(rect.width).toBeGreaterThan(0);
    expect(rect.height).toBeGreaterThan(0);

    expect(screen.getByText("Parcel 451")).toBeInTheDocument();
    expect(screen.getByText("parcel-transfer")).toBeInTheDocument();
    expect(fitViewSpy).toHaveBeenCalled();
    expect(consoleError).not.toHaveBeenCalled();
  });
});
