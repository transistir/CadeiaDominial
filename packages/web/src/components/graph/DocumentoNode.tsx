import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import type { DocumentoData } from "../../graph/types";
import "./DocumentoNode.css";

export interface DocumentoNodeData extends DocumentoData, Record<string, unknown> {
  label?: string;
}

export type DocumentoReactFlowNode = Node<DocumentoNodeData, "documento">;

export function DocumentoNode({ data }: NodeProps<DocumentoReactFlowNode>) {
  const tipoClass = `documento-node--${data.tipo}`;

  return (
    <div className={`documento-node ${tipoClass}`} data-testid="documento-node">
      <Handle type="target" position={Position.Left} />
      <div className="documento-node__badge" data-tipo={data.tipo}>
        {data.tipo}
      </div>
      <div className="documento-node__numero">{data.numero}</div>
      <div className="documento-node__meta">
        <span className="documento-node__cartorio">{data.cartorioId}</span>
        <span className="documento-node__data">{data.data}</span>
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
