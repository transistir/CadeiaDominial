import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import type { FimCadeiaData } from "../../graph/types";
import "./FimCadeiaNode.css";

export interface FimCadeiaNodeData extends FimCadeiaData, Record<string, unknown> {
  label?: string;
}

export type FimCadeiaReactFlowNode = Node<FimCadeiaNodeData, "fimCadeia">;

const CLASSIFICATION_LABEL: Record<FimCadeiaData["classificacao"], string> = {
  origem_lidima: "Origem Lídima",
  sem_origem: "Sem Origem",
  inconclusa: "Inconclusa",
  destacamento_publico: "Destacamento Público",
  nao_resolvida: "Não Resolvida",
  outra: "Outra"
};

export function FimCadeiaNode({ data }: NodeProps<FimCadeiaReactFlowNode>) {
  const className = `fim-cadeia-node fim-cadeia-node--${data.classificacao}`;

  return (
    <div
      className={className}
      data-classificacao={data.classificacao}
      data-testid="fim-cadeia-node"
    >
      <Handle type="target" position={Position.Left} />
      <div className="fim-cadeia-node__icon" aria-hidden="true">
        ⏹
      </div>
      <div className="fim-cadeia-node__label">{data.label ?? "Fim de Cadeia"}</div>
      <div className="fim-cadeia-node__classification">
        {CLASSIFICATION_LABEL[data.classificacao]}
      </div>
      {data.especificacao && (
        <div className="fim-cadeia-node__classification">{data.especificacao}</div>
      )}
    </div>
  );
}
