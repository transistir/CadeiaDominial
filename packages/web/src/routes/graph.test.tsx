import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import GraphRoute from "./graph";

const fitViewSpy = vi.hoisted(() => vi.fn());

vi.mock("@xyflow/react", () => ({
  ReactFlow: ({ nodes, edges, fitView, children }: any) => {
    if (fitView) {
      fitViewSpy();
    }

    return (
      <div data-testid="reactflow">
        <div data-testid="nodes">
          {nodes.map((node: any) => (
            <div key={node.id} data-node-id={node.id}>
              {node.data?.label ?? node.id}
            </div>
          ))}
        </div>
        <div data-testid="edges">
          {edges.map((edge: any) => (
            <div key={edge.id} data-edge-id={edge.id}>
              {edge.id}
            </div>
          ))}
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
  const originalClientWidth = Object.getOwnPropertyDescriptor(
    HTMLElement.prototype,
    "clientWidth"
  );
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
      // eslint-disable-next-line @typescript-eslint/no-dynamic-delete
      delete (HTMLElement.prototype as any).clientWidth;
    }
    if (originalClientHeight) {
      Object.defineProperty(HTMLElement.prototype, "clientHeight", originalClientHeight);
    } else {
      // eslint-disable-next-line @typescript-eslint/no-dynamic-delete
      delete (HTMLElement.prototype as any).clientHeight;
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
