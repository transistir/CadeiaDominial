import { describe, it, expect } from "vitest";
import {
  tokenizeValues,
  parseInserts,
  normalizeNumero,
  haToCentiares,
  toIso,
  nullIfEmpty,
  parseOrigemText,
  normalizeTipoFimCadeia,
  mapCri,
  mapPessoa,
  mapImovel,
  mapDocumento,
  mapLancamento,
  mapLancamentoTipo,
  mapTis,
} from "../legacy-fit";

const NOW = "2026-06-29T00:00:00.000Z";

describe("tokenizeValues", () => {
  it("parses NULL, integers and floats", () => {
    expect(tokenizeValues("1,NULL,42,-3,18393.94")).toEqual([
      1,
      null,
      42,
      -3,
      18393.94,
    ]);
  });

  it("parses quoted strings and preserves empty strings", () => {
    expect(tokenizeValues("'abc',''," + "'  spaced  '")).toEqual([
      "abc",
      "",
      "  spaced  ",
    ]);
  });

  it("handles embedded commas, parens and escaped quotes", () => {
    const inner = "1,'Fazenda ABC, Lote (2), o''dado','MT'";
    expect(tokenizeValues(inner)).toEqual([
      1,
      "Fazenda ABC, Lote (2), o'dado",
      "MT",
    ]);
  });

  it("strips ::type casts on quoted literals", () => {
    expect(tokenizeValues("'2025-01-01T00:00:00Z'::timestamptz,5")).toEqual([
      "2025-01-01T00:00:00Z",
      5,
    ]);
  });

  it("coerces unquoted postgres booleans t/f to 1/0", () => {
    expect(tokenizeValues("t,f,true,false")).toEqual([1, 0, 1, 0]);
  });
});

describe("parseInserts", () => {
  it("extracts positional tuples for a table, ignoring other tables", () => {
    const sql = [
      "INSERT INTO dominial_pessoas VALUES(1,NULL,'',NULL,'','','Ze');",
      "INSERT INTO dominial_cartorios VALUES(1,'1º RI','063453','End','(66) 1','a@b','CIDADE','MT','CRI');",
      "INSERT INTO dominial_pessoas VALUES(8,NULL,'',NULL,'','','Malandrao');",
    ].join("\n");
    const pessoas = parseInserts(sql, "dominial_pessoas");
    expect(pessoas).toHaveLength(2);
    expect(pessoas[0]).toEqual([1, null, "", null, "", "", "Ze"]);
    expect(pessoas[1]![6]).toBe("Malandrao");
  });

  it("handles multi-line string literals", () => {
    const sql =
      "INSERT INTO dominial_lancamento VALUES(1,'line one\nline two; with ; semis',NULL,4);";
    const rows = parseInserts(sql, "dominial_lancamento");
    expect(rows).toHaveLength(1);
    expect(rows[0]![1]).toBe("line one\nline two; with ; semis");
    expect(rows[0]![3]).toBe(4);
  });
});

describe("scalar helpers", () => {
  it("normalizeNumero keeps digits only", () => {
    expect(normalizeNumero("M6726")).toBe("6726");
    expect(normalizeNumero("3-A/155")).toBe("3155");
    expect(normalizeNumero(null)).toBe("");
  });

  it("haToCentiares multiplies hectares by 10000", () => {
    expect(haToCentiares(18393.94)).toBe(183939400);
    expect(haToCentiares(684)).toBe(6840000);
    expect(haToCentiares(null)).toBeNull();
  });

  it("toIso expands partial dates and passes full timestamps through", () => {
    expect(toIso("2025-07-07", NOW)).toBe("2025-07-07T00:00:00.000Z");
    expect(toIso("1992", NOW)).toBe("1992-01-01T00:00:00.000Z");
    expect(toIso("2025-08-13T22:05:17.770637Z", NOW)).toBe(
      "2025-08-13T22:05:17.770637Z"
    );
    expect(toIso(null, NOW)).toBe(NOW);
  });

  it("nullIfEmpty trims and nulls empties", () => {
    expect(nullIfEmpty("")).toBeNull();
    expect(nullIfEmpty("  ")).toBeNull();
    expect(nullIfEmpty(" x ")).toBe("x");
  });

  it("normalizeTipoFimCadeia maps to the v2 CHECK set", () => {
    expect(normalizeTipoFimCadeia("destacamento_publico")).toBe(
      "destacamento_publico"
    );
    expect(normalizeTipoFimCadeia("")).toBeNull();
    expect(normalizeTipoFimCadeia("algo_estranho")).toBe("outra");
  });
});

describe("parseOrigemText", () => {
  it("splits multiple origins and classifies by prefix", () => {
    const tokens = parseOrigemText("M517; M526; T2108");
    expect(tokens).toEqual([
      { raw: "M517", tipo: "matricula", numero: "517" },
      { raw: "M526", tipo: "matricula", numero: "526" },
      { raw: "T2108", tipo: "transcricao", numero: "2108" },
    ]);
  });

  it("treats bare numbers as transcricao and free text as fim_cadeia", () => {
    expect(parseOrigemText("1835")).toEqual([
      { raw: "1835", tipo: "transcricao", numero: "1835" },
    ]);
    expect(parseOrigemText("Estado do Paraná")).toEqual([
      { raw: "Estado do Paraná", tipo: "fim_cadeia", numero: null },
    ]);
    expect(parseOrigemText(null)).toEqual([]);
    expect(parseOrigemText("")).toEqual([]);
  });
});

describe("column-order assumptions (validated against the dump)", () => {
  it("maps dominial_cartorios → cri (cidade before estado, tipo last)", () => {
    // id, nome, cns, endereco, telefone, email, CIDADE, ESTADO, tipo
    const row = parseInserts(
      "INSERT INTO dominial_cartorios VALUES(1,'1º Registro de Imóveis de Alta Floresta','063453','Ariosto da Riva','(66) 3521-2303','adm@x.com','ALTA FLORESTA','MT','CRI');",
      "dominial_cartorios"
    )[0]!;
    const cri = mapCri(row, NOW);
    expect(cri).toMatchObject({
      id: 1,
      nome: "1º Registro de Imóveis de Alta Floresta",
      cns_codigo: "063453",
      cidade: "ALTA FLORESTA",
      uf: "MT",
      endereco: "Ariosto da Riva",
      tipo: "CRI",
    });
  });

  it("maps dominial_imovel → imovel (cartorio[5], proprietario[6], tis[7])", () => {
    // id, nome, matricula, observacoes, data_cadastro, cartorio, proprietario, tis, tipo_doc, arquivado
    const row = parseInserts(
      "INSERT INTO dominial_imovel VALUES(4,'Fazenda Espigão','6726','','2025-07-07',1355,9,614,'matricula',0);",
      "dominial_imovel"
    )[0]!;
    const imovel = mapImovel(row, NOW);
    expect(imovel).toMatchObject({
      id: 4,
      nome: "Fazenda Espigão",
      observacoes: null,
      data_cadastro: "2025-07-07",
      cri_id: 1355,
      proprietario_id: 9,
      arquivado: 0,
      created_at: "2025-07-07T00:00:00.000Z",
    });
  });
});

describe("full row → new-schema transforms", () => {
  it("transforms a documento row (numero normalized, tipo_id 2 → matricula)", () => {
    const row = parseInserts(
      "INSERT INTO dominial_documento VALUES(4,'M6726','2024-01-01','1','1','origem text','2025-07-07',1355,4,2,'obs',NULL,NULL,NULL,NULL,NULL);",
      "dominial_documento"
    )[0]!;
    expect(mapDocumento(row, NOW)).toEqual({
      id: 4,
      tipo: "matricula",
      numero: "6726",
      numero_raw: "M6726",
      data: "2024-01-01",
      livro: "1",
      folha: "1",
      data_cadastro: "2025-07-07",
      cri_id: 1355,
      created_at: "2025-07-07T00:00:00.000Z",
    });
  });

  it("transforms a transcricao documento (tipo_id 3 → transcricao)", () => {
    const row = parseInserts(
      "INSERT INTO dominial_documento VALUES(113,'T2108','2025-07-11','3A','155','o','2025-07-11',1305,5,3,'obs',NULL,1355,1305,NULL,NULL);",
      "dominial_documento"
    )[0]!;
    const doc = mapDocumento(row, NOW);
    expect(doc.tipo).toBe("transcricao");
    expect(doc.numero).toBe("2108");
    expect(doc.cri_id).toBe(1305);
  });

  it("transforms a lancamento row (area ha → centiares, numero_lancamento NULL)", () => {
    // id,data,_,area,_,detalhes,data_cadastro,_,documento,_,tipo,...
    const row = parseInserts(
      "INSERT INTO dominial_lancamento VALUES(99,'2022-08-09',NULL,2228.56,NULL,'detalhe aqui','2025-07-07',NULL,4,NULL,2,1355,'1992-10-21',NULL,NULL,0,'0','Doação',NULL,NULL,'M517; M526','R6M6726',NULL,NULL,NULL,NULL);",
      "dominial_lancamento"
    )[0]!;
    const l = mapLancamento(row, NOW);
    expect(l.id).toBe(99);
    expect(l.data).toBe("2022-08-09");
    expect(l.area_centiares).toBe(22285600);
    expect(l.detalhes).toBe("detalhe aqui");
    expect(l.documento_id).toBe(4);
    expect(l.tipo_id).toBe(2);
    expect(l.forma).toBe("Doação");
    expect(l.numero_lancamento).toBeNull();
    expect(l.valor_transacao_centavos).toBeNull();
    expect(l.created_at).toBe("2025-07-07T00:00:00.000Z");
  });

  it("transforms a pessoa row keeping only nome (Q5 PII removal)", () => {
    const row = parseInserts(
      "INSERT INTO dominial_pessoas VALUES(9,NULL,'',NULL,'','','Pedro Gezualdo');",
      "dominial_pessoas"
    )[0]!;
    expect(mapPessoa(row, NOW)).toEqual({
      id: 9,
      nome: "Pedro Gezualdo",
      created_at: NOW,
      updated_at: NOW,
    });
  });

  it("transforms a tis row (area ha → centiares, terra_referencia_id kept)", () => {
    const row = parseInserts(
      "INSERT INTO dominial_tis VALUES(1,'101','Kokama','2025-07-05',1,18393.94,'AM','Acapuri de Cima');",
      "dominial_tis"
    )[0]!;
    expect(mapTis(row, NOW)).toMatchObject({
      id: 1,
      codigo: "101",
      etnia: "Kokama",
      terra_referencia_id: 1,
      area_centiares: 183939400,
      estado: "AM",
      nome: "Acapuri de Cima",
    });
  });

  it("generates a human nome and copies requer_* flags for lancamento_tipo", () => {
    const row = parseInserts(
      "INSERT INTO dominial_lancamentotipo VALUES(3,'inicio_matricula',0,0,0,0,1,0,1,0,1,0);",
      "dominial_lancamentotipo"
    )[0]!;
    const t = mapLancamentoTipo(row);
    expect(t.id).toBe(3);
    expect(t.tipo).toBe("inicio_matricula");
    expect(t.nome).toBe("Início de Matrícula");
    // all 10 flags present and 0/1
    const flagKeys = Object.keys(t).filter((k) => k.startsWith("requer_"));
    expect(flagKeys).toHaveLength(10);
    for (const k of flagKeys) expect([0, 1]).toContain((t as Record<string, unknown>)[k]);
  });
});
