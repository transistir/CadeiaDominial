import { ReactFlowProvider, type Node, type NodeProps } from "@xyflow/react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { DocumentoTipo } from "../../graph/types";
import { DocumentoNode, type DocumentoNodeData } from "./DocumentoNode";

type DocumentoReactFlowNode = Node<DocumentoNodeData, "documento">;

const baseData: DocumentoNodeData = {
  numero: "M123",
  tipo: "matricula",
  cartorioId: "cartorio-1",
  data: "2024-01-15",
};

function renderDocumentoNode(data: Partial<DocumentoNodeData> = {}) {
  return render(
    <ReactFlowProvider>
      <DocumentoNode
        {...({
          id: "doc-1",
          type: "documento",
          data: { ...baseData, ...data },
        } as NodeProps<DocumentoReactFlowNode>)}
      />
    </ReactFlowProvider>,
  );
}

function expectTipoClass(tipo: DocumentoTipo) {
  expect(screen.getByTestId("documento-node")).toHaveClass(`documento-node--${tipo}`);
}

describe("DocumentoNode", () => {
  it("renders numero, tipo, cartorio, data", () => {
    renderDocumentoNode();

    expect(screen.getByText("M123")).toBeInTheDocument();
    expect(screen.getByText("matricula")).toBeInTheDocument();
    expect(screen.getByText("cartorio-1")).toBeInTheDocument();
    expect(screen.getByText("2024-01-15")).toBeInTheDocument();
  });

  it("applies correct color class for matricula tipo", () => {
    renderDocumentoNode({ tipo: "matricula" });

    expectTipoClass("matricula");
  });

  it("applies correct color class for transcricao tipo", () => {
    renderDocumentoNode({ tipo: "transcricao" });

    expectTipoClass("transcricao");
  });

  it("applies correct color class for averbacao tipo", () => {
    renderDocumentoNode({ tipo: "averbacao" });

    expectTipoClass("averbacao");
  });

  it("matches snapshot for matricula tipo", () => {
    const { container } = renderDocumentoNode({ tipo: "matricula", numero: "M123" });

    expect(container.firstChild).toMatchSnapshot();
  });

  it("matches snapshot for transcricao tipo", () => {
    const { container } = renderDocumentoNode({ tipo: "transcricao", numero: "T456" });

    expect(container.firstChild).toMatchSnapshot();
  });

  it("matches snapshot for averbacao tipo", () => {
    const { container } = renderDocumentoNode({ tipo: "averbacao", numero: "AV7" });

    expect(container.firstChild).toMatchSnapshot();
  });

  it("renders Handle components for target and source positions", () => {
    const { container } = renderDocumentoNode();

    expect(container.querySelector(".react-flow__handle-left.target")).toBeInTheDocument();
    expect(container.querySelector(".react-flow__handle-right.source")).toBeInTheDocument();
  });
});
