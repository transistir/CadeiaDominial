import { ReactFlowProvider, Position, useStoreApi, type EdgeProps } from "@xyflow/react";
import { render, screen } from "@testing-library/react";
import { useEffect, useRef, type ReactElement, type ReactNode } from "react";
import { describe, expect, it } from "vitest";
import type { OrigemTipo } from "../../graph/types";
import { OrigemEdge, type OrigemReactFlowEdge } from "./OrigemEdge";

const baseProps = {
  id: "e1",
  type: "origem",
  source: "doc-1",
  target: "doc-2",
  sourceX: 0,
  sourceY: 0,
  targetX: 100,
  targetY: 100,
  sourcePosition: Position.Right,
  targetPosition: Position.Left
} satisfies Omit<EdgeProps<OrigemReactFlowEdge>, "data">;

function ReactFlowTestShell({ children }: { children: ReactNode }): ReactElement {
  const store = useStoreApi();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (ref.current) {
      store.setState({ domNode: ref.current });
    }
  }, [store]);

  return (
    <div className="react-flow" ref={ref}>
      <svg>{children}</svg>
      <div className="react-flow__edgelabel-renderer" />
    </div>
  );
}

function renderEdge(props: Partial<EdgeProps<OrigemReactFlowEdge>> = {}) {
  return render(
    <ReactFlowProvider>
      <ReactFlowTestShell>
        <OrigemEdge
          {...({
            ...baseProps,
            ...props
          } as EdgeProps<OrigemReactFlowEdge>)}
        />
      </ReactFlowTestShell>
    </ReactFlowProvider>
  );
}

function expectTipoClass(tipo: OrigemTipo) {
  expect(screen.getByTestId("origem-edge-label")).toHaveClass(`origem-edge--${tipo}`);
}

describe("OrigemEdge", () => {
  it("renders BaseEdge with path", () => {
    const { container } = renderEdge({ data: { tipoOrigem: "matricula" } });

    const edgePath = container.querySelector(".react-flow__edge-path");

    expect(edgePath).toBeInTheDocument();
    expect(edgePath).toHaveClass("origem-edge", "origem-edge--matricula");
    expect(edgePath).toHaveAttribute("d");
  });

  it("renders label for matricula", () => {
    renderEdge({ data: { tipoOrigem: "matricula" } });

    expect(screen.getByTestId("origem-edge-label")).toHaveTextContent("M");
  });

  it("renders label for transcricao", () => {
    renderEdge({ data: { tipoOrigem: "transcricao" } });

    expect(screen.getByTestId("origem-edge-label")).toHaveTextContent("T");
  });

  it("renders label for fim_cadeia", () => {
    renderEdge({ data: { tipoOrigem: "fim_cadeia" } });

    expect(screen.getByTestId("origem-edge-label")).toHaveTextContent("Fim");
  });

  it("no label rendered when data.tipoOrigem is missing", () => {
    renderEdge({ data: {} });

    expect(screen.queryByTestId("origem-edge-label")).not.toBeInTheDocument();
  });

  it("no label rendered when data is missing", () => {
    renderEdge();

    expect(screen.queryByTestId("origem-edge-label")).not.toBeInTheDocument();
  });

  it("applies correct class for matricula tipo", () => {
    renderEdge({ data: { tipoOrigem: "matricula" } });

    expectTipoClass("matricula");
  });

  it("applies correct class for transcricao tipo", () => {
    renderEdge({ data: { tipoOrigem: "transcricao" } });

    expectTipoClass("transcricao");
  });

  it("applies correct class for fim_cadeia tipo", () => {
    renderEdge({ data: { tipoOrigem: "fim_cadeia" } });

    expectTipoClass("fim_cadeia");
  });

  it("matches snapshot for matricula edge", () => {
    const { container } = renderEdge({ data: { tipoOrigem: "matricula" } });

    expect(container.firstChild).toMatchSnapshot();
  });

  it("matches snapshot for fim_cadeia edge (dashed style)", () => {
    const { container } = renderEdge({ data: { tipoOrigem: "fim_cadeia" } });

    expect(container.firstChild).toMatchSnapshot();
  });
});
