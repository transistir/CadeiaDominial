/**
 * legacy-fit.ts — Load the legacy PostgreSQL data dump into the NEW
 * Drizzle/D1 schema (T-300).
 *
 * The dump (`data.cleaned.core.no-auth.no-unistr.sql`) is DATA-ONLY: every
 * line is a positional `INSERT INTO dominial_<table> VALUES(...);` with no
 * column names and no CREATE TABLE. The new schema is a redesign, so this is
 * a TRANSFORMATION, not a 1:1 copy. We parse the positional tuples, map them
 * onto the new tables, and load them into the local miniflare D1 SQLite file
 * via better-sqlite3.
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
 *   [0]id→id  [6]nome→nome   ([1..5] cpf/rg/nascimento/email/telefone dropped)
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
 *   [0]id→id  [1]data→data  [3]area(ha)→area_centiares  [5]detalhes→detalhes
 *   [6]data_cadastro→data_cadastro  [8]documento_id→documento_id
 *   [10]tipo_id→tipo_id  [13]descricao→descricao  [17]forma→forma
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
 * dominial_tis → tis            [0]id [1]codigo [2]etnia [3]data_cadastro
 *   [4]terra_referencia_id [5]area(ha)→area_centiares [6]estado [7]nome
 * dominial_terraindigenareferencia → terra_indigena_referencia
 *   [0]id [1]codigo [2]nome [3]etnia [4]municipio [5]area(ha)→area_ha_centiares
 *   [6]fase [7]modalidade [8]coordenacao_regional [9..13]dates [14]created
 *   [15]updated [16]estado
 * dominial_documentotipo → (lookup only) {1:transmissao,2:matricula,3:transcricao}
 *
 * NOT LOADED (no clean v2 home — documented decision):
 *   dominial_documentoimportado (import bookkeeping), dominial_fimcadeia
 *   (end-of-chain *definition* presets — superseded by origem_fim_cadeia rows).
 * ─────────────────────────────────────────────────────────────────────────
 */

import { readFileSync, readdirSync, mkdirSync, writeFileSync } from "node:fs";
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
      out.push(buf === "" ? null : buf);
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
  cartorio: { id: 0, nome: 1, cns: 2, endereco: 3, cidade: 6, estado: 7, tipo: 8 },
  pessoa: { id: 0, nome: 6 },
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
    detalhes: 5,
    dataCadastro: 6,
    documentoId: 8,
    tipoId: 10,
    cartorioOrigemId: 11,
    descricao: 13,
    forma: 17,
    titulo: 19,
    origemText: 20,
    dataTransmissao: 23,
    folhaTransmissao: 24,
    livroTransmissao: 25,
  },
  lancPessoa: { id: 0, papel: 1, nomeDigitado: 2, lancamentoId: 3, pessoaId: 4 },
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
    codigo: 1,
    etnia: 2,
    dataCadastro: 3,
    terraRefId: 4,
    area: 5,
    estado: 6,
    nome: 7,
  },
  terra: {
    id: 0,
    codigo: 1,
    nome: 2,
    etnia: 3,
    municipio: 4,
    area: 5,
    fase: 6,
    modalidade: 7,
    coordRegional: 8,
    dataRegularizada: 9,
    dataHomologada: 10,
    dataDeclarada: 11,
    dataDelimitada: 12,
    dataEmEstudo: 13,
    createdAt: 14,
    updatedAt: 15,
    estado: 16,
  },
} as const;

// ──────────────────────────────── Mappers ──────────────────────────────────
// Each returns a plain object whose keys are the v2 column names. Pure
// functions of a parsed row (+ small lookups) so they are unit-testable.

export function mapCri(r: SqlValue[], now: string) {
  const tipo = String(r[C.cartorio.tipo] ?? "CRI");
  return {
    id: r[C.cartorio.id] as number,
    nome: (nullIfEmpty(r[C.cartorio.nome]) ?? `Cartório ${r[C.cartorio.id]}`),
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
  return {
    id: r[C.pessoa.id] as number,
    nome: nullIfEmpty(r[C.pessoa.nome]) ?? `Pessoa ${r[C.pessoa.id]}`,
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
    arquivado: r[C.imovel.arquivado] ? 1 : 0,
    created_at: toIso(r[C.imovel.dataCadastro], now),
    updated_at: toIso(r[C.imovel.dataCadastro], now),
  };
}

export function mapDocumento(r: SqlValue[], now: string) {
  const tipoId = r[C.documento.tipoId] as number;
  const tipo = DOCUMENTO_TIPO_BY_ID[tipoId] === "transcricao" ? "transcricao" : "matricula";
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
  return {
    id: r[C.lancamento.id] as number,
    data: nullIfEmpty(r[C.lancamento.data]),
    valor_transacao_centavos: null as number | null,
    area_centiares: haToCentiares(r[C.lancamento.area]),
    detalhes: nullIfEmpty(r[C.lancamento.detalhes]),
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
    flags[keys[i]!] = r[C.lancTipo.requerStart + i] ? 1 : 0;
  return {
    id: r[C.lancTipo.id] as number,
    tipo,
    nome: LANCAMENTO_TIPO_NOME[tipo] ?? tipo,
    ...flags,
  };
}

export function mapTis(r: SqlValue[], now: string) {
  return {
    id: r[C.tis.id] as number,
    codigo: String(r[C.tis.codigo] ?? r[C.tis.id]),
    etnia: nullIfEmpty(r[C.tis.etnia]) ?? "—",
    data_cadastro: nullIfEmpty(r[C.tis.dataCadastro]) ?? now.slice(0, 10),
    terra_referencia_id: (r[C.tis.terraRefId] as number | null) ?? null,
    area_centiares: haToCentiares(r[C.tis.area]),
    estado: nullIfEmpty(r[C.tis.estado]),
    nome: nullIfEmpty(r[C.tis.nome]),
    created_at: now,
    updated_at: now,
  };
}

export function mapTerra(r: SqlValue[], now: string) {
  return {
    id: r[C.terra.id] as number,
    codigo: String(r[C.terra.codigo] ?? r[C.terra.id]),
    nome: nullIfEmpty(r[C.terra.nome]) ?? `Terra ${r[C.terra.id]}`,
    etnia: nullIfEmpty(r[C.terra.etnia]),
    estado: nullIfEmpty(r[C.terra.estado]),
    municipio: nullIfEmpty(r[C.terra.municipio]),
    area_ha_centiares: haToCentiares(r[C.terra.area]),
    fase: nullIfEmpty(r[C.terra.fase]),
    modalidade: nullIfEmpty(r[C.terra.modalidade]),
    coordenacao_regional: nullIfEmpty(r[C.terra.coordRegional]),
    data_regularizada: nullIfEmpty(r[C.terra.dataRegularizada]),
    data_homologada: nullIfEmpty(r[C.terra.dataHomologada]),
    data_declarada: nullIfEmpty(r[C.terra.dataDeclarada]),
    data_delimitada: nullIfEmpty(r[C.terra.dataDelimitada]),
    data_em_estudo: nullIfEmpty(r[C.terra.dataEmEstudo]),
    created_at: toIso(r[C.terra.createdAt], now),
    updated_at: toIso(r[C.terra.updatedAt], now),
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
  if (process.env.LEGACY_DUMP) return resolve(process.env.LEGACY_DUMP);
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
    try {
      readFileSync(c);
      return c;
    } catch {
      /* try next */
    }
  }
  throw new Error(
    `Dump not found. Set LEGACY_DUMP=<path>. Tried:\n  ${candidates.join("\n  ")}`
  );
}

function resolveSqlitePath(): string {
  if (process.env.D1_SQLITE) return resolve(process.env.D1_SQLITE);
  const here = dirname(fileURLToPath(import.meta.url));
  const dir = resolve(
    here,
    "../../packages/api/.wrangler/state/v3/d1/miniflare-D1DatabaseObject"
  );
  const files = readdirSync(dir).filter(
    (f) => f.endsWith(".sqlite") && !f.includes("metadata")
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
  errors: ColumnError[]
): number {
  if (rows.length === 0) return 0;
  const cols = Object.keys(rows[0]!);
  const stmt = db.prepare(
    `INSERT INTO ${table} (${cols.join(", ")}) VALUES (${cols
      .map(() => "?")
      .join(", ")})`
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
}

function run(): Report {
  const dumpPath = resolveDumpPath();
  const sqlitePath = resolveSqlitePath();
  const now = new Date().toISOString();
  const sql = readFileSync(dumpPath, "utf8");

  console.log(`legacy-fit: dump   = ${dumpPath}`);
  console.log(`legacy-fit: target = ${sqlitePath}\n`);

  // ── parse ──
  const rawCartorios = parseInserts(sql, DOMINIAL.cartorios);
  const rawPessoas = parseInserts(sql, DOMINIAL.pessoas);
  const rawImovel = parseInserts(sql, DOMINIAL.imovel);
  const rawDocumento = parseInserts(sql, DOMINIAL.documento);
  const rawLancamento = parseInserts(sql, DOMINIAL.lancamento);
  const rawLancPessoa = parseInserts(sql, DOMINIAL.lancamentopessoa);
  const rawLancTipo = parseInserts(sql, DOMINIAL.lancamentotipo);
  const rawOrigemFim = parseInserts(sql, DOMINIAL.origemfimcadeia);
  const rawTis = parseInserts(sql, DOMINIAL.tis);
  const rawTerra = parseInserts(sql, DOMINIAL.terra);

  // ── lookups ──
  const pessoaNomeById = new Map<number, string>();
  for (const r of rawPessoas)
    pessoaNomeById.set(
      r[C.pessoa.id] as number,
      nullIfEmpty(r[C.pessoa.nome]) ?? `Pessoa ${r[C.pessoa.id]}`
    );

  // documento lookup: (imovelId|tipo|normNumero) → documentoId, and per-imovel docs
  const docByKey = new Map<string, number>();
  const docsByImovel = new Map<number, { id: number; numeroNorm: string; tipo: string }[]>();
  for (const r of rawDocumento) {
    const id = r[C.documento.id] as number;
    const imovelId = r[C.documento.imovelId] as number;
    const tipo =
      DOCUMENTO_TIPO_BY_ID[r[C.documento.tipoId] as number] === "transcricao"
        ? "transcricao"
        : "matricula";
    const numeroNorm = normalizeNumero(r[C.documento.numero]);
    docByKey.set(`${imovelId}|${tipo}|${numeroNorm}`, id);
    if (!docsByImovel.has(imovelId)) docsByImovel.set(imovelId, []);
    docsByImovel.get(imovelId)!.push({ id, numeroNorm, tipo });
  }
  // documento → imovel + cri lookups (for lancamento origem cri fallback)
  const docImovel = new Map<number, number>();
  const docCri = new Map<number, number>();
  for (const r of rawDocumento) {
    docImovel.set(r[C.documento.id] as number, r[C.documento.imovelId] as number);
    docCri.set(r[C.documento.id] as number, r[C.documento.cartorioId] as number);
  }

  // ── build new-schema rows ──
  const criRows = rawCartorios.map((r) => mapCri(r, now));
  const pessoaRows = rawPessoas.map((r) => mapPessoa(r, now));
  const tisRows = rawTis.map((r) => mapTis(r, now));
  const terraRows = rawTerra.map((r) => mapTerra(r, now));
  const lancTipoRows = rawLancTipo.map((r) => mapLancamentoTipo(r));
  const imovelRows = rawImovel.map((r) => mapImovel(r, now));
  const documentoRows = rawDocumento.map((r) => mapDocumento(r, now));
  const lancamentoRows = rawLancamento.map((r) => mapLancamento(r, now));

  // imovel_documento: every (imovel, documento) pair; mark the current one.
  const imovelDocRows: Record<string, unknown>[] = [];
  for (const r of rawImovel) {
    const imovelId = r[C.imovel.id] as number;
    const matriculaNorm = normalizeNumero(r[C.imovel.matricula]);
    const principal =
      r[C.imovel.tipoDocPrincipal] === "transcricao" ? "transcricao" : "matricula";
    const docs = docsByImovel.get(imovelId) ?? [];
    let currentDocId: number | null = null;
    for (const d of docs)
      if (
        currentDocId === null &&
        d.numeroNorm === matriculaNorm &&
        d.tipo === principal
      )
        currentDocId = d.id;
    for (const d of docs)
      imovelDocRows.push({
        imovel_id: imovelId,
        documento_id: d.id,
        is_documento_atual: d.id === currentDocId ? 1 : 0,
        created_at: now,
      });
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

  // origem (+ origem_fim_cadeia), built per lancamento from origem text and
  // overlaid with the dominial_origemfimcadeia table by indice.
  const ofcByLanc = new Map<number, Map<number, SqlValue[]>>();
  for (const r of rawOrigemFim) {
    const lancId = r[C.origemFim.lancamentoId] as number;
    const indice = r[C.origemFim.indice] as number;
    if (!ofcByLanc.has(lancId)) ofcByLanc.set(lancId, new Map());
    ofcByLanc.get(lancId)!.set(indice, r);
  }

  interface OrigemRow {
    lancamentoId: number;
    criId: number;
    documentoId: number | null;
    indice: number;
    tipo: string;
    numero: string | null;
    numeroRaw: string;
    fim?: SqlValue[];
  }
  const origemRows: OrigemRow[] = [];
  for (const r of rawLancamento) {
    const lancId = r[C.lancamento.id] as number;
    const docId = (r[C.lancamento.documentoId] as number | null) ?? null;
    const imovelId = docId !== null ? (docImovel.get(docId) ?? null) : null;
    const criId =
      (r[C.lancamento.cartorioOrigemId] as number | null) ??
      (docId !== null ? (docCri.get(docId) ?? null) : null);
    if (criId === null) continue; // origem.cri_id is NOT NULL; skip if unknown

    const byIndice = new Map<number, OrigemRow>();
    const tokens = parseOrigemText(r[C.lancamento.origemText]);
    tokens.forEach((tok, i) => {
      let matchedDoc: number | null = null;
      if (tok.numero !== null && imovelId !== null)
        matchedDoc = docByKey.get(`${imovelId}|${tok.tipo}|${tok.numero}`) ?? null;
      byIndice.set(i, {
        lancamentoId: lancId,
        criId,
        documentoId: matchedDoc,
        indice: i,
        tipo: tok.tipo,
        numero: tok.numero,
        numeroRaw: tok.raw,
      });
    });

    // overlay end-of-chain entries by indice
    const ofc = ofcByLanc.get(lancId);
    if (ofc)
      for (const [indice, fimRow] of ofc) {
        const existing = byIndice.get(indice);
        if (existing) {
          existing.tipo = "fim_cadeia";
          existing.documentoId = null;
          existing.fim = fimRow;
        } else {
          byIndice.set(indice, {
            lancamentoId: lancId,
            criId,
            documentoId: null,
            indice,
            tipo: "fim_cadeia",
            numero: null,
            numeroRaw: nullIfEmpty(fimRow[C.origemFim.tipoFim]) ?? "fim_cadeia",
            fim: fimRow,
          });
        }
      }

    for (const o of [...byIndice.values()].sort((a, b) => a.indice - b.indice))
      origemRows.push(o);
  }

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
      dumpRows: rawDocumento.length,
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
      `INSERT INTO origem (lancamento_id, cri_id, documento_id, indice, tipo, numero, numero_raw, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
    );
    const fimStmt = db.prepare(
      `INSERT INTO origem_fim_cadeia (origem_id, tipo_fim_cadeia, classificacao_fim_cadeia, especificacao_fim_cadeia) VALUES (?, ?, ?, ?)`
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
          now
        );
        origemLoaded++;
        if (o.fim) {
          fimStmt.run(
            Number(res.lastInsertRowid),
            normalizeTipoFimCadeia(o.fim[C.origemFim.tipoFim]),
            nullIfEmpty(o.fim[C.origemFim.classificacao]),
            nullIfEmpty(o.fim[C.origemFim.especificacao])
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
    stats.push({ table: "origem", dumpRows: origemRows.length, loaded: origemLoaded });
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
  return { stats, fkViolations, columnErrors: errors };
}

// ──────────────────────────────── Report ───────────────────────────────────

function buildReport(report: Report, dumpPath: string): string {
  const { stats, fkViolations, columnErrors } = report;
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
      fkViolations.length === 0 ? "✓ no violations" : `✗ ${fkViolations.length} violations`
    }`
  );
  lines.push(
    `- **NOT NULL / CHECK** (enforced at insert): ${
      columnErrors.length === 0 ? "✓ no violations" : `✗ ${columnErrors.length} rejected rows`
    }`
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
      `  ${flag} ${s.table.padEnd(26)} ${String(s.loaded).padStart(5)} / ${s.dumpRows}`
    );
  }
  const fkOk = report.fkViolations.length === 0;
  const colOk = report.columnErrors.length === 0;
  console.log("");
  console.log(`FK check        : ${fkOk ? "✓ no violations" : `✗ ${report.fkViolations.length}`}`);
  console.log(`NOT NULL/CHECK  : ${colOk ? "✓ no violations" : `✗ ${report.columnErrors.length}`}`);
  if (!colOk)
    for (const e of report.columnErrors.slice(0, 10))
      console.log(`   [${e.table}] ${e.message}`);
  if (!fkOk) console.log(JSON.stringify(report.fkViolations.slice(0, 10), null, 2));

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
