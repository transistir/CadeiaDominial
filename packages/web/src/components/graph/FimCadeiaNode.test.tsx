import { ReactFlowProvider, type Node, type NodeProps } from "@xyflow/react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { FimCadeiaClassificacao } from "../../graph/types";
import { FimCadeiaNode, type FimCadeiaNodeData } from "./FimCadeiaNode";

type FimCadeiaReactFlowNode = Node<FimCadeiaNodeData, "fimCadeia">;

const baseData: FimCadeiaNodeData = {
  classificacao: "origem_lidima"
};

function renderFimCadeiaNode(data: Partial<FimCadeiaNodeData> = {}) {
  return render(
    <ReactFlowProvider>
      <FimCadeiaNode
        {...({
          id: "fim-1",
          type: "fimCadeia",
          data: { ...baseData, ...data }
        } as NodeProps<FimCadeiaReactFlowNode>)}
      />
    </ReactFlowProvider>
  );
}

function expectClassificacaoClass(classificacao: FimCadeiaClassificacao) {
  expect(screen.getByTestId("fim-cadeia-node")).toHaveClass(`fim-cadeia-node--${classificacao}`);
}

describe("FimCadeiaNode", () => {
  it("renders the classification label for origem_lidima", () => {
    renderFimCadeiaNode({ classificacao: "origem_lidima" });

    expect(screen.getByText("Origem Lídima")).toBeInTheDocument();
  });

  it("renders the classification label for sem_origem", () => {
    renderFimCadeiaNode({ classificacao: "sem_origem" });

    expect(screen.getByText("Sem Origem")).toBeInTheDocument();
  });

  it("renders the classification label for inconclusa", () => {
    renderFimCadeiaNode({ classificacao: "inconclusa" });

    expect(screen.getByText("Inconclusa")).toBeInTheDocument();
  });

  it("applies correct class for origem_lidima", () => {
    renderFimCadeiaNode({ classificacao: "origem_lidima" });

    expectClassificacaoClass("origem_lidima");
  });

  it("applies correct class for sem_origem", () => {
    renderFimCadeiaNode({ classificacao: "sem_origem" });

    expectClassificacaoClass("sem_origem");
  });

  it("applies correct class for inconclusa", () => {
    renderFimCadeiaNode({ classificacao: "inconclusa" });

    expectClassificacaoClass("inconclusa");
  });

  it("renders target Handle only", () => {
    const { container } = renderFimCadeiaNode();

    const handles = container.querySelectorAll(".react-flow__handle");

    expect(handles).toHaveLength(1);
    expect(container.querySelector(".react-flow__handle-left.target")).toBeInTheDocument();
    expect(container.querySelector(".react-flow__handle-right.source")).not.toBeInTheDocument();
  });

  it("matches snapshot for origem_lidima classification", () => {
    const { container } = renderFimCadeiaNode({ classificacao: "origem_lidima" });

    expect(container.firstChild).toMatchSnapshot();
  });

  it("matches snapshot for sem_origem classification", () => {
    const { container } = renderFimCadeiaNode({ classificacao: "sem_origem" });

    expect(container.firstChild).toMatchSnapshot();
  });

  it("matches snapshot for inconclusa classification", () => {
    const { container } = renderFimCadeiaNode({ classificacao: "inconclusa" });

    expect(container.firstChild).toMatchSnapshot();
  });
});
