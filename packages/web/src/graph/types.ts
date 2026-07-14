export type DocumentoTipo = "matricula" | "transcricao" | "averbacao";
export type FimCadeiaClassificacao =
  | "origem_lidima"
  | "sem_origem"
  | "inconclusa"
  | "destacamento_publico"
  | "nao_resolvida"
  | "outra";
export type OrigemTipo = "matricula" | "transcricao" | "fim_cadeia";

export interface DocumentoData {
  numero: string;
  tipo: DocumentoTipo;
  cartorioId: string;
  data: string | null;
}

export interface FimCadeiaData {
  classificacao: FimCadeiaClassificacao;
  label?: string;
  especificacao?: string;
}

export type GraphNode =
  | { id: string; type: "documento"; label: string; data: DocumentoData }
  | { id: string; type: "fimCadeia"; label: string; data: FimCadeiaData };

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  data?: { tipoOrigem: OrigemTipo };
}

export interface GraphJson {
  nodes: GraphNode[];
  edges: GraphEdge[];
}
