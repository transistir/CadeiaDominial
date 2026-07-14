/**
 * legacy-fit.ts — Load the legacy PostgreSQL data dump into the NEW
 * Drizzle/D1 schema (T-300).
 *
 * Supports both the old positional INSERT dump
 * (`data.cleaned.core.no-auth.no-unistr.sql`) and production PostgreSQL dumps
 * whose table data is emitted as `COPY public.<table> (...) FROM stdin`.
 * The new schema is a redesign, so this is a TRANSFORMATION, not a 1:1 copy.
 * We parse the rows, map them onto the new tables, and load them into the
 * local miniflare D1 SQLite file via better-sqlite3.
 *
 * Run:  pnpm legacy-fit            (from the worktree root)
 *   or  node legacy-fit.ts         (from scripts/migration/)
 * Env:  LEGACY_DUMP=<path>         override the dump location
 *       D1_SQLITE=<path>           override the target SQLite file
 *
 * PATH note: pnpm/node live at /root/.hermes/node/bin in this environment;
 * the script itself just calls `node` (Node 22 strips TS types natively).
 *
 * ─────────────────────────────────────────────────────────────────────────
 * COLUMN-ORDER + MAPPING TABLE
 * ─────────────────────────────────────────────────────────────────────────
 * Positional column order was derived from docs/legacy-django/03-database-
 * models.md and VALIDATED empirically against the dump (type signatures, FK
 * hit-rates, value ranges). legacy ids are PRESERVED as new ids, so no FK
 * remapping is needed.
 *
 * dominial_cartorios → cri
 *   [0]id→id  [1]nome→nome  [2]cns→cns_codigo  [3]endereco→endereco
 *   [6]cidade→cidade  [7]estado→uf  [8]tipo→tipo (all 'CRI')
 *   ([4]telefone, [5]email dropped — no home in v2)
 *
 * dominial_pessoas → pessoa   (Q5 removed all PII except nome)
 *   [0]id→id  [1]nome→nome   ([2..6] cpf/rg/nascimento/email/telefone dropped)
 *
 * dominial_imovel → imovel (+ tis_imovel + imovel_documento)
 *   [0]id→id  [1]nome→nome  [2]matricula→(used for is_documento_atual match)
 *   [3]observacoes→observacoes  [4]data_cadastro→data_cadastro
 *   [5]cartorio_id→cri_id  [6]proprietario_id→proprietario_id
 *   [7]terra_indigena_id→tis_imovel.tis_id  [9]arquivado→arquivado
 *   ([8]tipo_documento_principal used to pick the "current" documento)
 *
 * dominial_documento → documento (+ imovel_documento)
 *   [0]id→id  [1]numero→numero_raw / numero(digits)  [2]data→data
 *   [3]livro→livro  [4]folha→folha  [6]data_cadastro→data_cadastro
 *   [7]cartorio_id→cri_id  [8]imovel_id→imovel_documento.imovel_id
 *   [9]tipo_id→tipo (2='matricula',3='transcricao')  [10]observacoes (dropped)
 *   ([5]origem text, [11]nivel_manual, [12]cri_atual, [13]cri_origem,
 *    [14]classificacao_fim_cadeia, [15]sigla_patrimonio_publico dropped —
 *    chain origins live on lancamento/origem in v2)
 *
 * dominial_lancamento → lancamento (+ origem + origem_fim_cadeia)
 *   [0]id→id  [1]data→data  [3]area(ha)→area_centiares  [4]detalhes→detalhes
 *   [6]data_cadastro→data_cadastro  [8]documento_id→documento_id
 *   [10]tipo_id→tipo_id  [13]descricao→descricao
 *   [14]documento_origem_id→origem.documento_id chain  [17]forma→forma
 *   [19]titulo→titulo  [20]origem text→origem rows  [23]→data_transmissao
 *   [24]→folha_transmissao  [25]→livro_transmissao
 *   ([11]cartorio_origem used as origem.cri_id fallback; [21] numero_lancamento
 *    raw code like "R6M6726" left NULL — v2 numero_lancamento is INTEGER and
 *    NULL is allowed during migration; valor_transacao has no populated source)
 *
 * dominial_lancamentopessoa → lancamento_pessoa
 *   [0]id→id  [1]papel(transmitente|adquirente)→papel  [2]nome_digitado→
 *   nome_verbatim (falls back to pessoa.nome)  [3]lancamento_id  [4]pessoa_id
 *
 * dominial_lancamentotipo → lancamento_tipo
 *   [0]id→id  [1]tipo→tipo (+ generated nome)  [2..11]→requer_* (positional,
 *   best-effort; flags drive UI only, not the graph)
 *
 * dominial_origemfimcadeia → origem_fim_cadeia (overlaid on origem by indice)
 *   [1]indice_origem  [3]tipo_fim_cadeia ('' → NULL)  [4]especificacao
 *   [5]classificacao  [6]lancamento_id
 *
 * dominial_tis → tis            [0]id [1]nome [2]codigo [3]etnia
 *   [4]data_cadastro [5]terra_referencia_id [6]area(ha)→area_centiares [7]estado
 * dominial_terraindigenareferencia → terra_indigena_referencia
 *   [0]id [1]codigo [2]nome [3]etnia [4]estado [5]municipio
 *   [6]area(ha)→area_ha_centiares [7]fase [8]modalidade
 *   [9]coordenacao_regional [10..14]dates [15]created [16]updated
 * dominial_documentotipo → (lookup only) {1:transmissao,2:matricula,3:transcricao}
 *
 * NOT LOADED (no clean v2 home — documented decision):
 *   dominial_documentoimportado (import bookkeeping), dominial_fimcadeia
 *   (end-of-chain *definition* presets — superseded by origem_fim_cadeia rows).
 * ─────────────────────────────────────────────────────────────────────────
 */

import {
  existsSync,
  readFileSync,
  readdirSync,
  mkdirSync,
  writeFileSync,
} from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import Database from "better-sqlite3";

// ───────────────────────────────── Parser ──────────────────────────────────

export type SqlValue = string | number | null;

/**
 * Tokenize the inner content of a single `VALUES(...)` tuple into typed
 * values. Handles: NULL, single-quoted strings (with `''` escapes and
 * embedded commas/parens/newlines), integers, floats, unquoted booleans
 * (`t`/`f`/`true`/`false`), and trailing `::type` casts on quoted literals
 * (e.g. `'2025-01-01'::timestamptz`).
 */
export function tokenizeValues(inner: string): SqlValue[] {
  const out: SqlValue[] = [];
  let i = 0;
  const n = inner.length;
  while (i < n) {
    while (i < n && /[\s,]/.test(inner[i]!)) i++;
    if (i >= n) break;
    if (inner[i] === "'") {
      i++;
      let buf = "";
      while (i < n) {
        if (inner[i] === "'") {
          if (inner[i + 1] === "'") {
            buf += "'";
            i += 2;
            continue;
          }
          i++;
          break;
        }
        buf += inner[i++];
      }
      // skip a trailing `::type` cast if present
      if (inner[i] === ":" && inner[i + 1] === ":") {
        i += 2;
        while (i < n && /[A-Za-z0-9_ ]/.test(inner[i]!) && inner[i] !== ",")
          i++;
      }
      out.push(buf);
    } else {
      let buf = "";
      while (i < n && inner[i] !== ",") buf += inner[i++];
      const tok = buf.trim();
      if (tok === "NULL" || tok === "") out.push(null);
      else if (tok === "t" || tok === "true") out.push(1);
      else if (tok === "f" || tok === "false") out.push(0);
      else if (/^-?\d+$/.test(tok)) out.push(Number.parseInt(tok, 10));
      else if (/^-?\d*\.\d+(?:[eE][-+]?\d+)?$/.test(tok))
        out.push(Number.parseFloat(tok));
      else out.push(tok);
    }
  }
  return out;
}

/**
 * Extract every `INSERT INTO <table> VALUES(...)` tuple from a SQL dump,
 * returning one parsed value array per row. The statement scanner is
 * quote-aware so it does not trip over commas, parens, or newlines inside
 * string literals.
 */
export function parseInserts(sql: string, table: string): SqlValue[][] {
  const prefix = `INSERT INTO ${table} VALUES`;
  const rows: SqlValue[][] = [];
  let idx = 0;
  for (;;) {
    const start = sql.indexOf(prefix, idx);
    if (start === -1) break;
    let p = start + prefix.length;
    while (p < sql.length && sql[p] !== "(") p++;
    p++; // step inside the opening paren
    const begin = p;
    let depth = 1;
    let inStr = false;
    while (p < sql.length && depth > 0) {
      const c = sql[p];
      if (inStr) {
        if (c === "'") {
          if (sql[p + 1] === "'") {
            p += 2;
            continue;
          }
          inStr = false;
        }
      } else if (c === "'") inStr = true;
      else if (c === "(") depth++;
      else if (c === ")") {
        depth--;
        if (depth === 0) break;
      }
      p++;
    }
    rows.push(tokenizeValues(sql.slice(begin, p)));
    idx = p;
  }
  return rows;
}

export interface CopyBlock {
  table: string;
  headers: string[];
  rows: SqlValue[][];
}

/** Decode PostgreSQL COPY text-format backslash escapes. */
function decodeCopyText(raw: string): string {
  let decoded = "";
  for (let i = 0; i < raw.length; i++) {
    const c = raw[i]!;
    if (c !== "\\" || i + 1 >= raw.length) {
      decoded += c;
      continue;
    }

    const escape = raw[++i]!;
    const simpleEscapes: Record<string, string> = {
      b: "\b",
      f: "\f",
      n: "\n",
      r: "\r",
      t: "\t",
      v: "\v",
      "\\": "\\",
    };
    if (escape in simpleEscapes) {
      decoded += simpleEscapes[escape];
      continue;
    }

    if (/[0-7]/.test(escape)) {
      let octal = escape;
      while (
        octal.length < 3 &&
        i + 1 < raw.length &&
        /[0-7]/.test(raw[i + 1]!)
      )
        octal += raw[++i]!;
      decoded += String.fromCharCode(Number.parseInt(octal, 8));
      continue;
    }

    if (
      escape === "x" &&
      i + 1 < raw.length &&
      /[0-9A-Fa-f]/.test(raw[i + 1]!)
    ) {
      let hex = raw[++i]!;
      if (i + 1 < raw.length && /[0-9A-Fa-f]/.test(raw[i + 1]!))
        hex += raw[++i]!;
      decoded += String.fromCharCode(Number.parseInt(hex, 16));
      continue;
    }

    // PostgreSQL treats a backslash before an otherwise unrecognized
    // character as quoting that character.
    decoded += escape;
  }
  return decoded;
}

/**
 * Convert one PostgreSQL COPY text field to the SqlValue representation.
 *
 * Boolean-looking tokens (`t`/`f`/`true`/`false`) are NOT coerced here. In
 * COPY text format a field's type is determined by its column, not its
 * spelling, so a `detalhes` value of "t" must stay the string "t" rather than
 * silently becoming the number 1. Boolean columns are coerced to 0/1 by the
 * column mappers via {@link toBool}.
 */
export function copyValue(raw: string): SqlValue {
  if (raw === "\\N") return null;
  const value = decodeCopyText(raw);
  // Preserve leading-zero identifiers such as CNS codes and document numbers.
  if (/^-?(?:0|[1-9]\d*)$/.test(value)) return Number.parseInt(value, 10);
  if (/^-?(?:\d+\.\d*|\d*\.\d+)(?:[eE][-+]?\d+)?$/.test(value))
    return Number.parseFloat(value);
  return value;
}

/**
 * Coerce a boolean-ish column value (COPY `t`/`f`/`true`/`false` or an INSERT
 * 0/1 integer) to 0/1. Used by column mappers that know their column is a
 * boolean — the generic parsers must not guess. Unknown/empty values default
 * to 0 so a stray non-empty string never reads as truthy just because it is
 * non-empty (e.g. `"f"` must not become 1).
 */
export function toBool(v: SqlValue): number {
  if (typeof v === "number") return v !== 0 ? 1 : 0;
  if (v === null) return 0;
  const s = String(v).trim().toLowerCase();
  return s === "t" || s === "true" ? 1 : 0;
}

/**
 * Parse PostgreSQL text-format COPY blocks. COPY text uses tabs as field
 * separators, `\\N` for NULL, `\\.` as the block terminator, and backslash
 * escapes (`\\t`, `\\n`, `\\\\`, octal, or hex) for special characters.
 * Literal quote characters are data in this format and are preserved.
 */
export function parseCopyFormat(sql: string, table?: string): CopyBlock[] {
  const blocks: CopyBlock[] = [];
  const header =
    /^COPY\s+public\.([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s+FROM\s+stdin;\r?$/gim;
  let match: RegExpExecArray | null;
  while ((match = header.exec(sql)) !== null) {
    const tableName = match[1]!;
    const includeBlock = table === undefined || tableName === table;
    const headers = match[2]!
      .split(",")
      .map((column) => column.trim().replace(/^"|"$/g, ""));
    const rows: SqlValue[][] = [];
    let cursor = header.lastIndex;
    if (sql[cursor] === "\r") cursor++;
    if (sql[cursor] === "\n") cursor++;
    let terminated = false;

    while (cursor <= sql.length) {
      let end = sql.indexOf("\n", cursor);
      if (end === -1) end = sql.length;
      let line = sql.slice(cursor, end);
      if (line.endsWith("\r")) line = line.slice(0, -1);
      cursor = end + 1;
      if (line === "\\.") {
        terminated = true;
        break;
      }
      if (includeBlock) {
        const fields = line.split("\t");
        if (fields.length !== headers.length) {
          throw new Error(
            `COPY public.${tableName}: row has ${fields.length} fields, expected ${headers.length} — malformed dump or unescaped tab/newline in data`,
          );
        }
        rows.push(fields.map(copyValue));
      }
      if (end === sql.length) break;
    }

    if (!terminated)
      throw new Error(`Unterminated COPY block for public.${tableName}`);
    header.lastIndex = cursor;
    if (includeBlock) blocks.push({ table: tableName, headers, rows });
  }
  return blocks;
}

/** Parse a table from either production COPY blocks or legacy INSERT rows. */
export function parseDumpTable(sql: string, table: string): SqlValue[][] {
  const copyBlocks = parseCopyFormat(sql, table);
  if (copyBlocks.length > 0) {
    isProductionFormat = true;
    return copyBlocks.flatMap((block) => block.rows);
  }
  return parseInserts(sql, table);
}

// ──────────────────────────────── Helpers ──────────────────────────────────

/** Normalize a cartório document number to digits only (for indexing). */
export function normalizeNumero(raw: SqlValue): string {
  if (raw === null) return "";
  return (String(raw).match(/\d+/g) ?? []).join("");
}

/** Map a documento `tipo_id` to the v2 enum value. */
export const DOCUMENTO_TIPO_BY_ID: Record<number, string> = {
  1: "transmissao",
  2: "matricula",
  3: "transcricao",
};

/** Convert hectares (legacy decimal) to integer centiares (1 ha = 10000 ca). */
export function haToCentiares(ha: SqlValue): number | null {
  if (ha === null || ha === "") return null;
  const n = typeof ha === "number" ? ha : Number.parseFloat(String(ha));
  if (!Number.isFinite(n)) return null;
  return Math.round(n * 10000);
}

/** A partial date ('YYYY-MM-DD' | 'YYYY-MM' | 'YYYY') → ISO8601 UTC instant. */
export function toIso(partial: SqlValue, fallback: string): string {
  if (partial === null || partial === "") return fallback;
  const s = String(partial).trim();
  if (/T.*Z?$/.test(s)) return s; // already a full timestamp
  const m = /^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?/.exec(s);
  if (!m) return fallback;
  const [, y, mo = "01", d = "01"] = m;
  return `${y}-${mo}-${d}T00:00:00.000Z`;
}

/** Empty string → NULL; otherwise the trimmed string. */
export function nullIfEmpty(v: SqlValue): string | null {
  if (v === null) return null;
  const s = String(v).trim();
  return s === "" ? null : s;
}

export interface OrigemToken {
  raw: string;
  /** 'matricula' | 'transcricao' | 'fim_cadeia' */
  tipo: string;
  /** digits-only numero, or null for fim_cadeia / non-numeric citations */
  numero: string | null;
}

/**
 * Parse a legacy `lancamento.origem` free-text field into ordered origem
 * tokens. Multiple origins are separated by `;`. Tokens starting with M/T are
 * matrículas/transcrições; bare numbers are treated as transcrições (legacy
 * convention); anything else (e.g. "Sem Origem", "Estado do Paraná",
 * "Destacamento Público:...") is an end-of-chain citation.
 */
export function parseOrigemText(text: SqlValue): OrigemToken[] {
  if (text === null) return [];
  const raw = String(text).trim();
  if (raw === "") return [];
  return raw
    .split(";")
    .map((t) => t.trim())
    .filter((t) => t.length > 0)
    .map((tok) => {
      const head = tok[0]!.toUpperCase();
      if (head === "M" && /\d/.test(tok))
        return { raw: tok, tipo: "matricula", numero: normalizeNumero(tok) };
      if (head === "T" && /\d/.test(tok))
        return { raw: tok, tipo: "transcricao", numero: normalizeNumero(tok) };
      if (/^\d+$/.test(tok))
        return { raw: tok, tipo: "transcricao", numero: tok };
      return { raw: tok, tipo: "fim_cadeia", numero: null };
    });
}

/** Legacy `tipo_fim_cadeia` value normalized for the v2 CHECK constraint. */
export function normalizeTipoFimCadeia(v: SqlValue): string | null {
  const s = nullIfEmpty(v);
  if (s === null) return null;
  return ["destacamento_publico", "sem_origem", "outra"].includes(s)
    ? s
    : "outra";
}

const LANCAMENTO_TIPO_NOME: Record<string, string> = {
  inicio_matricula: "Início de Matrícula",
  registro: "Registro",
  averbacao: "Averbação",
};

// ─────────────────────────── Column index maps ─────────────────────────────

const C = {
  cartorio: {
    id: 0,
    nome: 1,
    cns: 2,
    endereco: 3,
    cidade: 6,
    estado: 7,
    tipo: 8,
  },
  pessoa: { id: 0, nome: 1 },
  imovel: {
    id: 0,
    nome: 1,
    matricula: 2,
    observacoes: 3,
    dataCadastro: 4,
    cartorioId: 5,
    proprietarioId: 6,
    tisId: 7,
    tipoDocPrincipal: 8,
    arquivado: 9,
  },
  documento: {
    id: 0,
    numero: 1,
    data: 2,
    livro: 3,
    folha: 4,
    dataCadastro: 6,
    cartorioId: 7,
    imovelId: 8,
    tipoId: 9,
  },
  lancamento: {
    id: 0,
    data: 1,
    area: 3,
    detalhes: 4,
    dataCadastro: 6,
    documentoId: 8,
    tipoId: 10,
    cartorioOrigemId: 11,
    descricao: 13,
    documentoOrigemId: 14,
    ehInicioMatricula: 15,
    forma: 17,
    titulo: 19,
    origemText: 20,
    dataTransmissao: 23,
    folhaTransmissao: 24,
    livroTransmissao: 25,
  },
  lancPessoa: {
    id: 0,
    papel: 1,
    nomeDigitado: 2,
    lancamentoId: 3,
    pessoaId: 4,
  },
  lancTipo: { id: 0, tipo: 1, requerStart: 2 },
  origemFim: {
    indice: 1,
    tipoFim: 3,
    especificacao: 4,
    classificacao: 5,
    lancamentoId: 6,
  },
  tis: {
    id: 0,
    nome: 1,
    codigo: 2,
    etnia: 3,
    dataCadastro: 4,
    terraRefId: 5,
    area: 6,
    estado: 7,
  },
  terra: {
    id: 0,
    codigo: 1,
    nome: 2,
    etnia: 3,
    estado: 4,
    municipio: 5,
    area: 6,
    fase: 7,
    modalidade: 8,
    coordRegional: 9,
    dataRegularizada: 10,
    dataHomologada: 11,
    dataDeclarada: 12,
    dataDelimitada: 13,
    dataEmEstudo: 14,
    createdAt: 15,
    updatedAt: 16,
  },
} as const;

/** Set to true when `parseDumpTable` finds COPY-format blocks (production dump). */
let isProductionFormat = false;

/** Reset the production-format flag (for tests). */
export function resetFormatDetection(): void {
  isProductionFormat = false;
}

// ──────────────────────────────── Mappers ──────────────────────────────────
// Each returns a plain object whose keys are the v2 column names. Pure
// functions of a parsed row (+ small lookups) so they are unit-testable.

export function mapCri(r: SqlValue[], now: string) {
  const tipo = String(r[C.cartorio.tipo] ?? "CRI");
  return {
    id: r[C.cartorio.id] as number,
    nome: nullIfEmpty(r[C.cartorio.nome]) ?? `Cartório ${r[C.cartorio.id]}`,
    cns_codigo: nullIfEmpty(r[C.cartorio.cns]),
    cidade: nullIfEmpty(r[C.cartorio.cidade]),
    uf: nullIfEmpty(r[C.cartorio.estado]),
    endereco: nullIfEmpty(r[C.cartorio.endereco]),
    tipo: tipo === "CRI" || tipo === "OUTRO" ? tipo : "OUTRO",
    created_at: now,
    updated_at: now,
  };
}

export function mapPessoa(r: SqlValue[], now: string) {
  // Production COPY dumps have nome at index 1; legacy INSERT at index 6.
  // IMPORTANT: in legacy format index 1 is CPF — never use it as a nome
  // fallback (PII leak). Fall back to synthetic "Pessoa <id>" instead.
  const nome = isProductionFormat
    ? (nullIfEmpty(r[1]) ?? `Pessoa ${r[C.pessoa.id]}`)
    : (nullIfEmpty(r[6]) ?? `Pessoa ${r[C.pessoa.id]}`);
  return {
    id: r[C.pessoa.id] as number,
    nome,
    created_at: now,
    updated_at: now,
  };
}

export function mapImovel(r: SqlValue[], now: string) {
  return {
    id: r[C.imovel.id] as number,
    nome: nullIfEmpty(r[C.imovel.nome]) ?? `Imóvel ${r[C.imovel.id]}`,
    observacoes: nullIfEmpty(r[C.imovel.observacoes]),
    data_cadastro: nullIfEmpty(r[C.imovel.dataCadastro]),
    cri_id: r[C.imovel.cartorioId] as number,
    proprietario_id: (r[C.imovel.proprietarioId] as number | null) ?? null,
    arquivado: toBool(r[C.imovel.arquivado]),
    created_at: toIso(r[C.imovel.dataCadastro], now),
    updated_at: toIso(r[C.imovel.dataCadastro], now),
  };
}

export function mapDocumento(r: SqlValue[], now: string) {
  const tipoId = r[C.documento.tipoId] as number;
  const tipo =
    DOCUMENTO_TIPO_BY_ID[tipoId] === "transcricao"
      ? "transcricao"
      : "matricula";
  const numeroRaw = nullIfEmpty(r[C.documento.numero]);
  const numero = normalizeNumero(r[C.documento.numero]) || (numeroRaw ?? "0");
  return {
    id: r[C.documento.id] as number,
    tipo,
    numero,
    numero_raw: numeroRaw,
    data: nullIfEmpty(r[C.documento.data]),
    livro: nullIfEmpty(r[C.documento.livro]),
    folha: nullIfEmpty(r[C.documento.folha]),
    data_cadastro: nullIfEmpty(r[C.documento.dataCadastro]),
    cri_id: r[C.documento.cartorioId] as number,
    created_at: toIso(r[C.documento.dataCadastro], now),
  };
}

export function mapLancamento(r: SqlValue[], now: string) {
  // The legacy INSERT layout has 26 fields and stores detalhes at index 5;
  // production COPY has 27 fields and stores it at index 4.
  const detalhesIndex = r.length >= 27 ? C.lancamento.detalhes : 5;
  return {
    id: r[C.lancamento.id] as number,
    data: nullIfEmpty(r[C.lancamento.data]),
    valor_transacao_centavos: null as number | null,
    area_centiares: haToCentiares(r[C.lancamento.area]),
    detalhes: nullIfEmpty(r[detalhesIndex]),
    observacoes: null as string | null,
    data_cadastro: nullIfEmpty(r[C.lancamento.dataCadastro]),
    documento_id: (r[C.lancamento.documentoId] as number | null) ?? null,
    tipo_id: r[C.lancamento.tipoId] as number,
    descricao: nullIfEmpty(r[C.lancamento.descricao]),
    forma: nullIfEmpty(r[C.lancamento.forma]),
    titulo: nullIfEmpty(r[C.lancamento.titulo]),
    numero_lancamento: null as number | null,
    cartorio_transmissao_nome: null as string | null,
    livro_transmissao: nullIfEmpty(r[C.lancamento.livroTransmissao]),
    folha_transmissao: nullIfEmpty(r[C.lancamento.folhaTransmissao]),
    data_transmissao: nullIfEmpty(r[C.lancamento.dataTransmissao]),
    created_at: toIso(r[C.lancamento.dataCadastro], now),
  };
}

export function mapLancamentoTipo(r: SqlValue[]) {
  const tipo = String(r[C.lancTipo.tipo]);
  const flags: Record<string, number> = {};
  const keys = [
    "requer_detalhes",
    "requer_transmissao",
    "requer_cartorio_origem",
    "requer_data_origem",
    "requer_descricao",
    "requer_folha_origem",
    "requer_forma",
    "requer_livro_origem",
    "requer_observacao",
    "requer_titulo",
  ];
  for (let i = 0; i < keys.length; i++)
    flags[keys[i]!] = toBool(r[C.lancTipo.requerStart + i]);
  return {
    id: r[C.lancTipo.id] as number,
    tipo,
    nome: LANCAMENTO_TIPO_NOME[tipo] ?? tipo,
    ...flags,
  };
}

export function mapTis(r: SqlValue[], now: string) {
  // Legacy INSERT dumps: [0]id [1]codigo [2]etnia [3]dataCadastro [4]terraRefId [5]area [6]estado [7]nome
  // Production COPY:     [0]id [1]nome   [2]codigo [3]etnia       [4]dataCadastro [5]terraRefId [6]area [7]estado
  const c = isProductionFormat
    ? C.tis
    : {
        id: 0, codigo: 1, etnia: 2, dataCadastro: 3,
        terraRefId: 4, area: 5, estado: 6, nome: 7,
      };
  return {
    id: r[c.id] as number,
    codigo: String(r[c.codigo] ?? r[c.id]),
    etnia: nullIfEmpty(r[c.etnia]) ?? "—",
    data_cadastro: nullIfEmpty(r[c.dataCadastro]) ?? now.slice(0, 10),
    terra_referencia_id: (r[c.terraRefId] as number | null) ?? null,
    area_centiares: haToCentiares(r[c.area]),
    estado: nullIfEmpty(r[c.estado]),
    nome: nullIfEmpty(r[c.nome]),
    created_at: now,
    updated_at: now,
  };
}

export function mapTerra(r: SqlValue[], now: string) {
  // Legacy INSERT: [0]id [1]codigo [2]nome [3]etnia [4]municipio [5]area [6]fase ... [16]estado
  // Production COPY: [0]id [1]codigo [2]nome [3]etnia [4]estado [5]municipio [6]area ...
  const c = isProductionFormat
    ? C.terra
    : {
        id: 0, codigo: 1, nome: 2, etnia: 3, municipio: 4,
        area: 5, fase: 6, modalidade: 7, coordRegional: 8,
        dataRegularizada: 9, dataHomologada: 10, dataDeclarada: 11,
        dataDelimitada: 12, dataEmEstudo: 13, createdAt: 14,
        updatedAt: 15, estado: 16,
      };
  return {
    id: r[c.id] as number,
    codigo: String(r[c.codigo] ?? r[c.id]),
    nome: nullIfEmpty(r[c.nome]) ?? `Terra ${r[c.id]}`,
    etnia: nullIfEmpty(r[c.etnia]),
    estado: nullIfEmpty(r[c.estado]),
    municipio: nullIfEmpty(r[c.municipio]),
    area_ha_centiares: haToCentiares(r[c.area]),
    fase: nullIfEmpty(r[c.fase]),
    modalidade: nullIfEmpty(r[c.modalidade]),
    coordenacao_regional: nullIfEmpty(r[c.coordRegional]),
    data_regularizada: nullIfEmpty(r[c.dataRegularizada]),
    data_homologada: nullIfEmpty(r[c.dataHomologada]),
    data_declarada: nullIfEmpty(r[c.dataDeclarada]),
    data_delimitada: nullIfEmpty(r[c.dataDelimitada]),
    data_em_estudo: nullIfEmpty(r[c.dataEmEstudo]),
    created_at: toIso(r[c.createdAt], now),
    updated_at: toIso(r[c.updatedAt], now),
  };
}

// ──────────────────────────── Load orchestration ───────────────────────────

const DOMINIAL = {
  cartorios: "dominial_cartorios",
  pessoas: "dominial_pessoas",
  imovel: "dominial_imovel",
  documento: "dominial_documento",
  lancamento: "dominial_lancamento",
  lancamentopessoa: "dominial_lancamentopessoa",
  lancamentotipo: "dominial_lancamentotipo",
  origemfimcadeia: "dominial_origemfimcadeia",
  tis: "dominial_tis",
  terra: "dominial_terraindigenareferencia",
} as const;

/** Reverse-FK delete order, then forward insert order (for truncation). */
const LOAD_TABLES = [
  "origem_fim_cadeia",
  "origem",
  "lancamento_pessoa",
  "lancamento",
  "tis_imovel",
  "imovel_documento",
  "documento",
  "imovel",
  "lancamento_tipo",
  "pessoa",
  "tis",
  "terra_indigena_referencia",
  "cri",
];

function resolveDumpPath(): string {
  if (process.env.LEGACY_DUMP) {
    const path = resolve(process.env.LEGACY_DUMP);
    if (!existsSync(path)) {
      throw new Error(`LEGACY_DUMP set but file not found: ${path}`);
    }
    return path;
  }
  const here = dirname(fileURLToPath(import.meta.url));
  const root = resolve(here, "../.."); // worktree root (scripts/migration → root)
  const DUMP = "data.cleaned.core.no-auth.no-unistr.sql";
  // Per AGENTS.md the layout is <project>/{CadeiaDominial, worktrees/<task>},
  // so the dump lives in the sibling main checkout `../../CadeiaDominial`.
  const candidates = [
    resolve(root, DUMP),
    resolve(root, "../../CadeiaDominial", DUMP),
    resolve(root, "../CadeiaDominial", DUMP),
  ];
  for (const c of candidates) {
    if (existsSync(c)) return c;
  }
  throw new Error(
    `Dump not found. Set LEGACY_DUMP=<path>. Tried:\n  ${candidates.join("\n  ")}`,
  );
}

function resolveSqlitePath(): string {
  if (process.env.D1_SQLITE) return resolve(process.env.D1_SQLITE);
  const here = dirname(fileURLToPath(import.meta.url));
  const dir = resolve(
    here,
    "../../packages/api/.wrangler/state/v3/d1/miniflare-D1DatabaseObject",
  );
  const files = readdirSync(dir).filter(
    (f) => f.endsWith(".sqlite") && !f.includes("metadata"),
  );
  if (files.length === 0)
    throw new Error(`No D1 SQLite file under ${dir}. Run db:migrate:local.`);
  return join(dir, files[0]!);
}

interface ColumnError {
  table: string;
  message: string;
  sample: unknown;
}

interface LoadStat {
  table: string;
  dumpRows: number;
  loaded: number;
}

function insertRows(
  db: Database,
  table: string,
  rows: Record<string, unknown>[],
  errors: ColumnError[],
): number {
  if (rows.length === 0) return 0;
  const cols = Object.keys(rows[0]!);
  const stmt = db.prepare(
    `INSERT INTO ${table} (${cols.join(", ")}) VALUES (${cols.map(() => "?").join(", ")})`,
  );
  let loaded = 0;
  for (const row of rows) {
    try {
      stmt.run(...cols.map((c) => row[c]));
      loaded++;
    } catch (e) {
      errors.push({
        table,
        message: e instanceof Error ? e.message : String(e),
        sample: row,
      });
    }
  }
  return loaded;
}

interface Report {
  stats: LoadStat[];
  fkViolations: unknown[];
  columnErrors: ColumnError[];
  unmatchedOrigemTokens: number;
  mergedDocumentoRows: number;
}

export interface OrigemRow {
  lancamentoId: number;
  criId: number;
  documentoId: number | null;
  indice: number;
  tipo: string;
  numero: string | null;
  numeroRaw: string;
  fim?: SqlValue[];
}

export interface OrigemBuildResult {
  rows: OrigemRow[];
  unmatchedOrigemTokens: number;
}

function integerOrNull(value: SqlValue | undefined): number | null {
  if (typeof value === "number" && Number.isInteger(value)) return value;
  if (typeof value === "string" && /^\d+$/.test(value))
    return Number.parseInt(value, 10);
  return null;
}

/**
 * The v2 uniqueness key uses the digits-only document number. If distinct
 * legacy spellings normalize to the same (CRI, type, number), retain the
 * lowest legacy id and remap every reference to it.
 */
export function buildDocumentoIdRemap(
  rawDocumento: SqlValue[][],
): Map<number, number> {
  const idsByKey = new Map<string, number[]>();
  for (const r of rawDocumento) {
    const id = integerOrNull(r[C.documento.id]);
    const criId = integerOrNull(r[C.documento.cartorioId]);
    if (id === null || criId === null) continue;
    const tipo =
      DOCUMENTO_TIPO_BY_ID[integerOrNull(r[C.documento.tipoId]) ?? 0] ===
      "transcricao"
        ? "transcricao"
        : "matricula";
    const numero =
      normalizeNumero(r[C.documento.numero]) ||
      (nullIfEmpty(r[C.documento.numero]) ?? "0");
    const key = `${criId}|${tipo}|${numero}`;
    if (!idsByKey.has(key)) idsByKey.set(key, []);
    idsByKey.get(key)!.push(id);
  }

  const remap = new Map<number, number>();
  for (const ids of idsByKey.values()) {
    const canonicalId = Math.min(...ids);
    for (const id of ids) remap.set(id, canonicalId);
  }
  return remap;
}

/**
 * Build ordered origem rows. Production rows use documento_origem_id as the
 * authoritative edge and recursively follow the source document's own
 * lancamento. Legacy rows (or production rows without the FK) retain the
 * free-text matcher. Structured fim-de-cadeia rows are overlaid last.
 */
export function buildOrigemRows(
  rawLancamento: SqlValue[][],
  rawDocumento: SqlValue[][],
  rawOrigemFim: SqlValue[][],
  maxDepth = 50,
): OrigemBuildResult {
  interface DocumentoInfo {
    id: number;
    criId: number;
    tipo: "matricula" | "transcricao";
    numero: string;
    numeroRaw: string;
  }

  const documentoById = new Map<number, DocumentoInfo>();
  const documentoByKey = new Map<string, number>();
  for (const r of rawDocumento) {
    const id = integerOrNull(r[C.documento.id]);
    const criId = integerOrNull(r[C.documento.cartorioId]);
    if (id === null || criId === null) continue;
    const tipo =
      DOCUMENTO_TIPO_BY_ID[integerOrNull(r[C.documento.tipoId]) ?? 0] ===
      "transcricao"
        ? "transcricao"
        : "matricula";
    const numeroRaw = nullIfEmpty(r[C.documento.numero]) ?? String(id);
    const numero = normalizeNumero(r[C.documento.numero]) || numeroRaw;
    documentoById.set(id, { id, criId, tipo, numero, numeroRaw });
    documentoByKey.set(`${criId}|${tipo}|${numero}`, id);
  }

  // A document may have many transactions. Prefer its explicit
  // inicio-matricula/origin-bearing transaction when choosing the edge that
  // continues the ancestry chain.
  const lancamentoByDocumento = new Map<number, SqlValue[]>();
  const ancestryScore = (r: SqlValue[]): number =>
    (integerOrNull(r[C.lancamento.documentoOrigemId]) !== null ? 2 : 0) +
    (toBool(r[C.lancamento.ehInicioMatricula]) ? 1 : 0);
  for (const r of rawLancamento) {
    const documentoId = integerOrNull(r[C.lancamento.documentoId]);
    if (documentoId === null) continue;
    const existing = lancamentoByDocumento.get(documentoId);
    if (!existing || ancestryScore(r) > ancestryScore(existing))
      lancamentoByDocumento.set(documentoId, r);
  }

  const fimByLancamento = new Map<number, Map<number, SqlValue[]>>();
  for (const r of rawOrigemFim) {
    const lancamentoId = integerOrNull(r[C.origemFim.lancamentoId]);
    const indice = integerOrNull(r[C.origemFim.indice]);
    if (lancamentoId === null || indice === null) continue;
    if (!fimByLancamento.has(lancamentoId))
      fimByLancamento.set(lancamentoId, new Map());
    fimByLancamento.get(lancamentoId)!.set(indice, r);
  }

  const rows: OrigemRow[] = [];
  let unmatchedOrigemTokens = 0;
  for (const lancamento of rawLancamento) {
    const lancamentoId = integerOrNull(lancamento[C.lancamento.id]);
    if (lancamentoId === null) continue;
    const documentoId = integerOrNull(lancamento[C.lancamento.documentoId]);
    const documentoOrigemId = integerOrNull(
      lancamento[C.lancamento.documentoOrigemId],
    );
    const rootCriId =
      integerOrNull(lancamento[C.lancamento.cartorioOrigemId]) ??
      (documentoId !== null
        ? (documentoById.get(documentoId)?.criId ?? null)
        : null);
    const byIndice = new Map<number, OrigemRow>();
    let nextIndice = 0;

    if (documentoOrigemId !== null) {
      const visited = new Set<number>();
      if (documentoId !== null) visited.add(documentoId);
      let sourceId: number | null = documentoOrigemId;
      for (let depth = 0; sourceId !== null && depth < maxDepth; depth++) {
        if (visited.has(sourceId)) break;
        visited.add(sourceId);
        const source = documentoById.get(sourceId);
        if (!source) break;
        byIndice.set(nextIndice, {
          lancamentoId,
          criId: source.criId ?? rootCriId,
          documentoId: source.id,
          indice: nextIndice,
          tipo: source.tipo,
          numero: source.numero,
          numeroRaw: source.numeroRaw,
        });
        nextIndice++;
        const sourceLancamento = lancamentoByDocumento.get(sourceId);
        sourceId = sourceLancamento
          ? integerOrNull(sourceLancamento[C.lancamento.documentoOrigemId])
          : null;
      }

      // The FK chain is authoritative for document links. Preserve only
      // additional non-document citations from the free-text field.
      for (const token of parseOrigemText(
        lancamento[C.lancamento.origemText],
      )) {
        if (token.tipo !== "fim_cadeia" || rootCriId === null) continue;
        byIndice.set(nextIndice, {
          lancamentoId,
          criId: rootCriId,
          documentoId: null,
          indice: nextIndice,
          tipo: token.tipo,
          numero: token.numero,
          numeroRaw: token.raw,
        });
        nextIndice++;
      }
    } else if (rootCriId !== null) {
      const tokens = parseOrigemText(lancamento[C.lancamento.origemText]);
      tokens.forEach((token, indice) => {
        let matchedDocumentoId: number | null = null;
        if (token.numero !== null) {
          matchedDocumentoId =
            documentoByKey.get(`${rootCriId}|${token.tipo}|${token.numero}`) ??
            null;
          if (matchedDocumentoId === null) unmatchedOrigemTokens++;
        }
        byIndice.set(indice, {
          lancamentoId,
          criId: rootCriId,
          documentoId: matchedDocumentoId,
          indice,
          tipo: token.tipo,
          numero: token.numero,
          numeroRaw: token.raw,
        });
      });
    }

    // Structured end-of-chain data remains authoritative at its legacy index.
    const fimRows = fimByLancamento.get(lancamentoId);
    if (fimRows)
      for (const [indice, fimRow] of fimRows) {
        const existing = byIndice.get(indice);
        if (existing) {
          existing.tipo = "fim_cadeia";
          existing.documentoId = null;
          existing.fim = fimRow;
        } else if (rootCriId !== null) {
          byIndice.set(indice, {
            lancamentoId,
            criId: rootCriId,
            documentoId: null,
            indice,
            tipo: "fim_cadeia",
            numero: null,
            numeroRaw: nullIfEmpty(fimRow[C.origemFim.tipoFim]) ?? "fim_cadeia",
            fim: fimRow,
          });
        }
      }

    for (const [indice, origem] of byIndice) {
      if (origem.documentoId !== null && origem.documentoId === documentoId)
        byIndice.delete(indice);
    }
    rows.push(...[...byIndice.values()].sort((a, b) => a.indice - b.indice));
  }

  return { rows, unmatchedOrigemTokens };
}

function run(): Report {
  const dumpPath = resolveDumpPath();
  const sqlitePath = resolveSqlitePath();
  const now = new Date().toISOString();
  const sql = readFileSync(dumpPath, "utf8");

  console.log(`legacy-fit: dump   = ${dumpPath}`);
  console.log(`legacy-fit: target = ${sqlitePath}\n`);

  // ── parse ──
  const rawCartorios = parseDumpTable(sql, DOMINIAL.cartorios);
  const rawPessoas = parseDumpTable(sql, DOMINIAL.pessoas);
  const rawImovel = parseDumpTable(sql, DOMINIAL.imovel);
  const rawDocumento = parseDumpTable(sql, DOMINIAL.documento);
  const rawLancamento = parseDumpTable(sql, DOMINIAL.lancamento);
  const rawLancPessoa = parseDumpTable(sql, DOMINIAL.lancamentopessoa);
  const rawLancTipo = parseDumpTable(sql, DOMINIAL.lancamentotipo);
  const rawOrigemFim = parseDumpTable(sql, DOMINIAL.origemfimcadeia);
  const rawTis = parseDumpTable(sql, DOMINIAL.tis);
  const rawTerra = parseDumpTable(sql, DOMINIAL.terra);

  const documentoIdRemap = buildDocumentoIdRemap(rawDocumento);
  const canonicalDocumentoRows = rawDocumento.filter((r) => {
    const id = integerOrNull(r[C.documento.id]);
    return id !== null && documentoIdRemap.get(id) === id;
  });
  const mergedDocumentoRows =
    rawDocumento.length - canonicalDocumentoRows.length;
  const migratedLancamentoRows = rawLancamento.map((r) => {
    const migrated = [...r];
    for (const index of [
      C.lancamento.documentoId,
      C.lancamento.documentoOrigemId,
    ]) {
      const id = integerOrNull(migrated[index]);
      if (id !== null) migrated[index] = documentoIdRemap.get(id) ?? id;
    }
    return migrated;
  });

  // ── lookups ──
  const pessoaNomeById = new Map<number, string>();
  for (const r of rawPessoas) {
    const pessoa = mapPessoa(r, now);
    pessoaNomeById.set(pessoa.id, pessoa.nome);
  }

  // documento lookup per imovel
  const docsByImovel = new Map<
    number,
    { id: number; numeroNorm: string; tipo: string }[]
  >();
  for (const r of rawDocumento) {
    const legacyId = r[C.documento.id] as number;
    const id = documentoIdRemap.get(legacyId) ?? legacyId;
    const imovelId = r[C.documento.imovelId] as number;
    const tipo =
      DOCUMENTO_TIPO_BY_ID[r[C.documento.tipoId] as number] === "transcricao"
        ? "transcricao"
        : "matricula";
    const numeroNorm = normalizeNumero(r[C.documento.numero]);
    if (!docsByImovel.has(imovelId)) docsByImovel.set(imovelId, []);
    docsByImovel.get(imovelId)!.push({ id, numeroNorm, tipo });
  }

  // ── build new-schema rows ──
  const criRows = rawCartorios.map((r) => mapCri(r, now));
  const pessoaRows = rawPessoas.map((r) => mapPessoa(r, now));
  const tisRows = rawTis.map((r) => mapTis(r, now));
  const terraRows = rawTerra.map((r) => mapTerra(r, now));
  const lancTipoRows = rawLancTipo.map((r) => mapLancamentoTipo(r));
  const imovelRows = rawImovel.map((r) => mapImovel(r, now));
  const documentoRows = canonicalDocumentoRows.map((r) => mapDocumento(r, now));
  const lancamentoRows = migratedLancamentoRows.map((r) =>
    mapLancamento(r, now),
  );

  // imovel_documento: every (imovel, documento) pair; mark the current one.
  const imovelDocRows: Record<string, unknown>[] = [];
  const imovelDocumentoPairs = new Set<string>();
  for (const r of rawImovel) {
    const imovelId = r[C.imovel.id] as number;
    const matriculaNorm = normalizeNumero(r[C.imovel.matricula]);
    const principal =
      r[C.imovel.tipoDocPrincipal] === "transcricao"
        ? "transcricao"
        : "matricula";
    const docs = docsByImovel.get(imovelId) ?? [];
    let currentDocId: number | null = null;
    for (const d of docs)
      if (
        currentDocId === null &&
        d.numeroNorm === matriculaNorm &&
        d.tipo === principal
      )
        currentDocId = d.id;
    for (const d of docs) {
      const pairKey = `${imovelId}|${d.id}`;
      if (imovelDocumentoPairs.has(pairKey)) continue;
      imovelDocumentoPairs.add(pairKey);
      imovelDocRows.push({
        imovel_id: imovelId,
        documento_id: d.id,
        is_documento_atual: d.id === currentDocId ? 1 : 0,
        created_at: now,
      });
    }
  }

  // tis_imovel: imovel → its terra_indigena (one membership per imovel)
  const tisImovelRows = rawImovel.map((r) => ({
    tis_id: r[C.imovel.tisId] as number,
    imovel_id: r[C.imovel.id] as number,
    created_at: now,
  }));

  // lancamento_pessoa
  const lancPessoaRows = rawLancPessoa.map((r) => {
    const pessoaId = (r[C.lancPessoa.pessoaId] as number | null) ?? null;
    const nomeVerbatim =
      nullIfEmpty(r[C.lancPessoa.nomeDigitado]) ??
      (pessoaId !== null ? pessoaNomeById.get(pessoaId) : undefined) ??
      "—";
    const papel = String(r[C.lancPessoa.papel]);
    return {
      id: r[C.lancPessoa.id] as number,
      papel,
      nome_verbatim: nomeVerbatim,
      lancamento_id: r[C.lancPessoa.lancamentoId] as number,
      pessoa_id: pessoaId,
      created_at: now,
    };
  });

  // origem (+ origem_fim_cadeia): recursively follow documento_origem_id,
  // falling back to legacy origem text when no FK is present.
  const origemBuild = buildOrigemRows(
    migratedLancamentoRows,
    canonicalDocumentoRows,
    rawOrigemFim,
  );
  const origemRows = origemBuild.rows;
  const unmatchedOrigemTokens = origemBuild.unmatchedOrigemTokens;

  // ── open db & load ──
  const db = new Database(sqlitePath);
  db.pragma("foreign_keys = OFF");
  db.pragma("journal_mode = WAL");

  const errors: ColumnError[] = [];
  const stats: LoadStat[] = [];

  const tx = db.transaction(() => {
    // truncate (reverse FK order) for idempotent re-runs
    for (const t of LOAD_TABLES) db.prepare(`DELETE FROM ${t}`).run();

    stats.push({
      table: "cri",
      dumpRows: rawCartorios.length,
      loaded: insertRows(db, "cri", criRows, errors),
    });
    stats.push({
      table: "terra_indigena_referencia",
      dumpRows: rawTerra.length,
      loaded: insertRows(db, "terra_indigena_referencia", terraRows, errors),
    });
    stats.push({
      table: "tis",
      dumpRows: rawTis.length,
      loaded: insertRows(db, "tis", tisRows, errors),
    });
    stats.push({
      table: "pessoa",
      dumpRows: rawPessoas.length,
      loaded: insertRows(db, "pessoa", pessoaRows, errors),
    });
    stats.push({
      table: "lancamento_tipo",
      dumpRows: rawLancTipo.length,
      loaded: insertRows(db, "lancamento_tipo", lancTipoRows, errors),
    });
    stats.push({
      table: "imovel",
      dumpRows: rawImovel.length,
      loaded: insertRows(db, "imovel", imovelRows, errors),
    });
    stats.push({
      table: "documento",
      dumpRows: canonicalDocumentoRows.length,
      loaded: insertRows(db, "documento", documentoRows, errors),
    });
    stats.push({
      table: "imovel_documento",
      dumpRows: imovelDocRows.length,
      loaded: insertRows(db, "imovel_documento", imovelDocRows, errors),
    });
    stats.push({
      table: "tis_imovel",
      dumpRows: tisImovelRows.length,
      loaded: insertRows(db, "tis_imovel", tisImovelRows, errors),
    });
    stats.push({
      table: "lancamento",
      dumpRows: rawLancamento.length,
      loaded: insertRows(db, "lancamento", lancamentoRows, errors),
    });
    stats.push({
      table: "lancamento_pessoa",
      dumpRows: rawLancPessoa.length,
      loaded: insertRows(db, "lancamento_pessoa", lancPessoaRows, errors),
    });

    // origem must be inserted before origem_fim_cadeia; capture generated ids
    const origemStmt = db.prepare(
      `INSERT INTO origem (lancamento_id, cri_id, documento_id, indice, tipo, numero, numero_raw, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
    );
    const fimStmt = db.prepare(
      `INSERT INTO origem_fim_cadeia (origem_id, tipo_fim_cadeia, classificacao_fim_cadeia, especificacao_fim_cadeia) VALUES (?, ?, ?, ?)`,
    );
    let origemLoaded = 0;
    let fimLoaded = 0;
    for (const o of origemRows) {
      try {
        const res = origemStmt.run(
          o.lancamentoId,
          o.criId,
          o.documentoId,
          o.indice,
          o.tipo,
          o.numero,
          o.numeroRaw,
          now,
        );
        origemLoaded++;
        if (o.fim) {
          fimStmt.run(
            Number(res.lastInsertRowid),
            normalizeTipoFimCadeia(o.fim[C.origemFim.tipoFim]),
            nullIfEmpty(o.fim[C.origemFim.classificacao]),
            nullIfEmpty(o.fim[C.origemFim.especificacao]),
          );
          fimLoaded++;
        }
      } catch (e) {
        errors.push({
          table: "origem",
          message: e instanceof Error ? e.message : String(e),
          sample: o,
        });
      }
    }
    stats.push({
      table: "origem",
      dumpRows: origemRows.length,
      loaded: origemLoaded,
    });
    stats.push({
      table: "origem_fim_cadeia",
      dumpRows: origemRows.filter((o) => o.fim).length,
      loaded: fimLoaded,
    });
  });
  tx();

  // ── integrity: FK check ──
  db.pragma("foreign_keys = ON");
  const fkViolations = db.pragma("foreign_key_check") as unknown[];

  db.close();
  return {
    stats,
    fkViolations,
    columnErrors: errors,
    unmatchedOrigemTokens,
    mergedDocumentoRows,
  };
}

// ──────────────────────────────── Report ───────────────────────────────────

function buildReport(report: Report, dumpPath: string): string {
  const {
    stats,
    fkViolations,
    columnErrors,
    unmatchedOrigemTokens,
    mergedDocumentoRows,
  } = report;
  const lines: string[] = [];
  lines.push("# Legacy-fit migration report (T-300)\n");
  lines.push(`Source dump: \`${dumpPath}\`\n`);
  lines.push("## Per-table row counts (loaded vs dump)\n");
  lines.push("| Table | Dump rows | Loaded | OK |");
  lines.push("| --- | ---: | ---: | :---: |");
  for (const s of stats) {
    const ok = s.loaded === s.dumpRows ? "✓" : "⚠";
    lines.push(`| ${s.table} | ${s.dumpRows} | ${s.loaded} | ${ok} |`);
  }
  lines.push("");
  lines.push("## Integrity checks\n");
  lines.push(
    `- **FK check** (PRAGMA foreign_key_check): ${
      fkViolations.length === 0
        ? "✓ no violations"
        : `✗ ${fkViolations.length} violations`
    }`,
  );
  lines.push(
    `- **NOT NULL / CHECK** (enforced at insert): ${
      columnErrors.length === 0
        ? "✓ no violations"
        : `✗ ${columnErrors.length} rejected rows`
    }`,
  );
  lines.push(`- **Unmatched origem tokens**: ${unmatchedOrigemTokens}`);
  lines.push(
    `- **Normalized duplicate documentos merged**: ${mergedDocumentoRows}`,
  );
  lines.push("");
  if (fkViolations.length > 0) {
    lines.push("### FK violations (first 20)\n");
    lines.push("```");
    lines.push(JSON.stringify(fkViolations.slice(0, 20), null, 2));
    lines.push("```");
  }
  if (columnErrors.length > 0) {
    lines.push("### Rejected rows (first 20)\n");
    lines.push("```");
    for (const e of columnErrors.slice(0, 20))
      lines.push(`[${e.table}] ${e.message}`);
    lines.push("```");
  }
  lines.push("");
  return lines.join("\n");
}

// ───────────────────────────────── main ────────────────────────────────────

function main(): void {
  const dumpPath = resolveDumpPath();
  const report = run();

  // console summary
  console.log("Per-table row counts (loaded vs dump):");
  for (const s of report.stats) {
    const flag = s.loaded === s.dumpRows ? "✓" : "⚠";
    console.log(
      `  ${flag} ${s.table.padEnd(26)} ${String(s.loaded).padStart(5)} / ${s.dumpRows}`,
    );
  }
  const fkOk = report.fkViolations.length === 0;
  const colOk = report.columnErrors.length === 0;
  console.log("");
  console.log(
    `FK check        : ${fkOk ? "✓ no violations" : `✗ ${report.fkViolations.length}`}`,
  );
  console.log(
    `NOT NULL/CHECK  : ${colOk ? "✓ no violations" : `✗ ${report.columnErrors.length}`}`,
  );
  console.log(`Unmatched origem: ${report.unmatchedOrigemTokens}`);
  console.log(`Merged documentos: ${report.mergedDocumentoRows}`);
  if (!colOk)
    for (const e of report.columnErrors.slice(0, 10))
      console.log(`   [${e.table}] ${e.message}`);
  if (!fkOk)
    console.log(JSON.stringify(report.fkViolations.slice(0, 10), null, 2));

  // write markdown report
  const here = dirname(fileURLToPath(import.meta.url));
  const reportDir = resolve(here, "../../migration_workspace/reports");
  mkdirSync(reportDir, { recursive: true });
  const reportPath = join(reportDir, "legacy-fit.md");
  writeFileSync(reportPath, buildReport(report, dumpPath), "utf8");
  console.log(`\nReport written to ${reportPath}`);

  if (!fkOk || !colOk) {
    console.error("\nlegacy-fit: FAILED — integrity checks did not pass.");
    process.exit(1);
  }
  console.log("\nlegacy-fit: OK");
}

// Run only when executed directly (not when imported by tests).
const invokedPath = process.argv[1] ? pathToFileURL(process.argv[1]).href : "";
if (import.meta.url === invokedPath) main();
