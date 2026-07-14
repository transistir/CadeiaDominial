import type {
  DocumentoData,
  DocumentoTipo,
  FimCadeiaClassificacao,
  FimCadeiaData,
  GraphEdge,
  GraphJson,
  GraphNode,
  OrigemTipo
} from "./types";

/**
 * Validate a graph JSON payload from an untrusted source (loader, network, file).
 * Returns a strongly-typed GraphJson so downstream code never has to re-narrow.
 *
 * Throws on:
 * - non-object payloads
 * - missing or non-array `nodes` / `edges`
 * - nodes / edges missing required string fields or domain data
 * - duplicate node or edge IDs
 * - edge endpoints that don't reference an existing node
 */
export function validateGraph(input: unknown): GraphJson {
  if (!isRecord(input)) {
    throw new Error("Graph must be an object");
  }

  if (!Array.isArray(input.nodes)) {
    throw new Error("Graph.nodes must be an array");
  }
  if (!Array.isArray(input.edges)) {
    throw new Error("Graph.edges must be an array");
  }

  const nodes: GraphNode[] = [];
  const nodeIds = new Set<string>();
  for (const [i, raw] of input.nodes.entries()) {
    if (!isRecord(raw)) {
      throw new Error(`nodes[${i}] must be an object`);
    }
    const id = requireNonEmptyString(raw.id, `nodes[${i}].id`);
    if (nodeIds.has(id)) {
      throw new Error(`Duplicate node ID: ${id}`);
    }
    nodeIds.add(id);
    nodes.push(validateNode(raw, i));
  }

  const edges: GraphEdge[] = [];
  for (const [i, raw] of input.edges.entries()) {
    if (!isRecord(raw)) {
      throw new Error(`edges[${i}] must be an object`);
    }
    edges.push(validateEdge(raw, i));
  }

  // Integrity: unique edge IDs and valid endpoint references
  const edgeIds = new Set<string>();
  for (const edge of edges) {
    if (edgeIds.has(edge.id)) {
      throw new Error(`Duplicate edge ID: ${edge.id}`);
    }
    edgeIds.add(edge.id);

    if (!nodeIds.has(edge.source)) {
      throw new Error(`Edge ${edge.id} references non-existent source: ${edge.source}`);
    }
    if (!nodeIds.has(edge.target)) {
      throw new Error(`Edge ${edge.id} references non-existent target: ${edge.target}`);
    }
  }

  return { nodes, edges };
}

function validateNode(raw: Record<string, unknown>, index: number): GraphNode {
  const path = `nodes[${index}]`;
  const id = requireNonEmptyString(raw.id, `${path}.id`);
  const label = requireString(raw.label, `${path}.label`);

  if (raw.type !== "documento" && raw.type !== "fimCadeia") {
    throw new Error(`${path}.type: invalid value ${formatValue(raw.type)}`);
  }

  if (raw.type === "documento") {
    requirePrefix(id, "doc-", `${path}.id`);
    if (raw.data === undefined) {
      throw new Error(`${path}.data: documento nodes must have a data object with numero, tipo, cartorioId, and data`);
    }
    return {
      id,
      label,
      type: "documento",
      data: validateDocumentoData(raw.data, `${path}.data`)
    };
  }

  requirePrefix(id, "fim-", `${path}.id`);
  if (raw.data === undefined) {
    throw new Error(`${path}.data: fimCadeia nodes must have a data object with classificacao`);
  }
  return {
    id,
    label,
    type: "fimCadeia",
    data: validateFimCadeiaData(raw.data, `${path}.data`)
  };
}

function validateDocumentoData(raw: unknown, path: string): DocumentoData {
  if (!isRecord(raw)) {
    throw new Error(`${path} must be an object`);
  }

  const numero = requireString(raw.numero, `${path}.numero`);
  const tipo = requireDocumentoTipo(raw.tipo, `${path}.tipo`);
  const cartorioId = requireString(raw.cartorioId, `${path}.cartorioId`);
  const data = requireIsoDateString(raw.data, `${path}.data`);

  return { numero, tipo, cartorioId, data };
}

function validateFimCadeiaData(raw: unknown, path: string): FimCadeiaData {
  if (!isRecord(raw)) {
    throw new Error(`${path} must be an object`);
  }

  return {
    classificacao: requireFimCadeiaClassificacao(raw.classificacao, `${path}.classificacao`),
    ...(raw.especificacao === undefined
      ? {}
      : { especificacao: requireString(raw.especificacao, `${path}.especificacao`) })
  };
}

function validateEdge(raw: Record<string, unknown>, index: number): GraphEdge {
  const path = `edges[${index}]`;
  const id = requireNonEmptyString(raw.id, `${path}.id`);
  const source = requireNonEmptyString(raw.source, `${path}.source`);
  const target = requireNonEmptyString(raw.target, `${path}.target`);

  if (raw.data === undefined) {
    return { id, source, target };
  }

  if (!isRecord(raw.data)) {
    throw new Error(`${path}.data must be an object`);
  }

  return {
    id,
    source,
    target,
    data: { tipoOrigem: requireOrigemTipo(raw.data.tipoOrigem, `${path}.data.tipoOrigem`) }
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function requireString(value: unknown, path: string): string {
  if (typeof value !== "string") {
    throw new Error(`${path} must be a string`);
  }
  return value;
}

function requireNonEmptyString(value: unknown, path: string): string {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error(`${path} must be a non-empty string`);
  }
  return value;
}

function requirePrefix(value: string, prefix: "doc-" | "fim-", path: string): void {
  if (!value.startsWith(prefix)) {
    throw new Error(`${path}: expected prefix '${prefix}', got '${value}'`);
  }
}

function requireDocumentoTipo(value: unknown, path: string): DocumentoTipo {
  if (value === "matricula" || value === "transcricao" || value === "averbacao") {
    return value;
  }
  throw new Error(`${path}: invalid value ${formatValue(value)}`);
}

function requireFimCadeiaClassificacao(value: unknown, path: string): FimCadeiaClassificacao {
  if (
    value === "origem_lidima" ||
    value === "sem_origem" ||
    value === "inconclusa" ||
    value === "destacamento_publico" ||
    value === "outra"
  ) {
    return value;
  }
  throw new Error(`${path}: invalid value ${formatValue(value)}`);
}

function requireOrigemTipo(value: unknown, path: string): OrigemTipo {
  if (value === "matricula" || value === "transcricao" || value === "fim_cadeia") {
    return value;
  }
  throw new Error(`${path}: invalid value ${formatValue(value)}`);
}

function requireIsoDateString(value: unknown, path: string): string {
  if (typeof value !== "string") {
    throw new Error(`${path} must be a string`);
  }
  if (!isIsoDateString(value)) {
    throw new Error(`${path}: invalid ISO date ${formatValue(value)}`);
  }
  return value;
}

function isIsoDateString(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d{3})?(?:Z|[+-]\d{2}:\d{2})?)?$/.test(value)) {
    return false;
  }

  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp);
}

function formatValue(value: unknown): string {
  if (typeof value === "string") {
    return `'${value}'`;
  }
  if (value === undefined) {
    return "undefined";
  }
  return JSON.stringify(value);
}
