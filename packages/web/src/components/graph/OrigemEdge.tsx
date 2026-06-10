import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  type Edge,
  type EdgeProps
} from "@xyflow/react";
import type { OrigemTipo } from "../../graph/types";
import "./OrigemEdge.css";

export interface OrigemEdgeData extends Record<string, unknown> {
  tipoOrigem?: OrigemTipo;
}

export type OrigemReactFlowEdge = Edge<OrigemEdgeData, "origem">;

const TIPO_LABEL: Record<OrigemTipo, string> = {
  matricula: "M",
  transcricao: "T",
  fim_cadeia: "Fim"
};

const TIPO_CLASS: Record<OrigemTipo, string> = {
  matricula: "origem-edge--matricula",
  transcricao: "origem-edge--transcricao",
  fim_cadeia: "origem-edge--fim_cadeia"
};

export function OrigemEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data
}: EdgeProps<OrigemReactFlowEdge>) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition
  });

  const tipo = data?.tipoOrigem;
  const labelText = tipo ? TIPO_LABEL[tipo] : "";
  const tipoClass = tipo ? TIPO_CLASS[tipo] : "";
  const edgeClass = tipoClass ? `origem-edge ${tipoClass}` : "origem-edge";

  return (
    <>
      <BaseEdge id={id} path={edgePath} className={edgeClass} />
      {labelText && (
        <EdgeLabelRenderer>
          <div
            className={`origem-edge__label ${tipoClass}`}
            style={{
              position: "absolute",
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`
            }}
            data-testid="origem-edge-label"
            data-tipo={tipo}
          >
            {labelText}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
