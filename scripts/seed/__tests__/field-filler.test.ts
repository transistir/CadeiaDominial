import { describe, it, expect, beforeEach } from "vitest";
import { generateChainTopology } from "../chain-topology.js";
import { fillFields, generateCpf, validateCpf, generateCnpj, validateCnpj } from "../field-filler.js";

describe("field-filler", () => {
  describe("generateCpf", () => {
    it("generates a valid CPF with correct check digits", () => {
      const cpf = generateCpf();
      expect(validateCpf(cpf)).toBe(true);
    });

    it("generates CPF in correct format (ddd.ddd.ddd-dd)", () => {
      const cpf = generateCpf();
      expect(cpf).toMatch(/^\d{3}\.\d{3}\.\d{3}-\d{2}$/);
    });

    it("generates invalid CPF when flag is set", () => {
      const invalidCpf = generateCpf(true);
      expect(validateCpf(invalidCpf)).toBe(false);
    });

    it("generates unique CPFs", () => {
      const cpfs = new Set<string>();
      for (let i = 0; i < 100; i++) {
        cpfs.add(generateCpf());
      }
      expect(cpfs.size).toBeGreaterThan(90); // Allow some collisions but expect most to be unique
    });
  });

  describe("generateCnpj", () => {
    it("generates a valid CNPJ with correct check digits", () => {
      const cnpj = generateCnpj();
      expect(validateCnpj(cnpj)).toBe(true);
    });

    it("generates CNPJ in correct format (dd.ddd.ddd/dddd-dd)", () => {
      const cnpj = generateCnpj();
      expect(cnpj).toMatch(/^\d{2}\.\d{3}\.\d{3}\/\d{4}-\d{2}$/);
    });

    it("generates unique CNPJs", () => {
      const cnpjs = new Set<string>();
      for (let i = 0; i < 100; i++) {
        cnpjs.add(generateCnpj());
      }
      expect(cnpjs.size).toBeGreaterThan(90);
    });
  });

  describe("fillFields", () => {
    let topology: ReturnType<typeof generateChainTopology>;

    beforeEach(() => {
      topology = generateChainTopology(12345, 5);
    });

    it("produces deterministic output with same seed", () => {
      const filled1 = fillFields(topology, 12345);
      const filled2 = fillFields(topology, 12345);

      expect(filled1.documentos).toEqual(filled2.documentos);
      expect(filled1.pessoas).toEqual(filled2.pessoas);
      expect(filled1.imoveis).toEqual(filled2.imoveis);
    });

    it("produces different output with different seeds", () => {
      const filled1 = fillFields(topology, 11111);
      const filled2 = fillFields(topology, 22222);

      // At least some values should differ
      const docsDiffer = filled1.documentos.some(
        (doc, i) => doc.numero !== filled2.documentos[i].numero || doc.data !== filled2.documentos[i].data
      );
      expect(docsDiffer).toBe(true);
    });

    it("produces deterministic output without explicit seed (uses chainId)", () => {
      const filled1 = fillFields(topology);
      const filled2 = fillFields(topology);

      expect(filled1.documentos).toEqual(filled2.documentos);
      expect(filled1.pessoas).toEqual(filled2.pessoas);
      expect(filled1.imoveis).toEqual(filled2.imoveis);
    });

    it("generates all topology documentos", () => {
      const filled = fillFields(topology, 12345);

      expect(filled.documentos.length).toBe(topology.documentos.length);
      for (const doc of topology.documentos) {
        expect(filled.documentos.some((d) => d.topologyId === doc.id)).toBe(true);
      }
    });

    it("generates pessoas with valid CPFs for pessoa física", () => {
      const filled = fillFields(topology, 12345);

      const pfPessoas = filled.pessoas.filter((p) => p.tipo === "pf");
      expect(pfPessoas.length).toBeGreaterThan(0);

      for (const pessoa of pfPessoas) {
        expect(validateCpf(pessoa.cpfCnpj)).toBe(true);
      }
    });

    it("generates pessoas with valid CNPJs for pessoa jurídica", () => {
      const filled = fillFields(topology, 12345);

      const pjPessoas = filled.pessoas.filter((p) => p.tipo === "pj");
      // PJ pessoas are random, so we may or may not have them
      if (pjPessoas.length > 0) {
        for (const pessoa of pjPessoas) {
          expect(validateCnpj(pessoa.cpfCnpj)).toBe(true);
        }
      }
    });

    it("generates documento dates that are monotonically increasing", () => {
      const filled = fillFields(topology, 12345);

      for (let i = 1; i < filled.documentos.length; i++) {
        const prevDate = new Date(filled.documentos[i - 1].data);
        const currDate = new Date(filled.documentos[i].data);
        expect(currDate.getTime()).toBeGreaterThan(prevDate.getTime());
      }
    });

    it("generates documento numero format matching tipo", () => {
      const filled = fillFields(topology, 12345);

      for (let i = 0; i < filled.documentos.length; i++) {
        const filledDoc = filled.documentos[i];
        const topoDoc = topology.documentos[i];

        if (topoDoc.tipo === "matricula") {
          expect(filledDoc.numero).toMatch(/^M-\d{5}$/);
        } else {
          expect(filledDoc.numero).toMatch(/^T-\d{5}$/);
        }
      }
    });

    it("generates unique documento numbers within chain", () => {
      const filled = fillFields(topology, 12345);

      const numeros = filled.documentos.map((d) => d.numero);
      const uniqueNumeros = new Set(numeros);
      expect(uniqueNumeros.size).toBe(numeros.length);
    });

    it("generates realistic person names", () => {
      const filled = fillFields(topology, 12345);

      const pfPessoas = filled.pessoas.filter((p) => p.tipo === "pf");
      expect(pfPessoas.length).toBeGreaterThan(0);

      // Verify names are realistic (have at least first and last name)
      for (const pessoa of pfPessoas) {
        const nameParts = pessoa.nome.trim().split(/\s+/);
        expect(nameParts.length).toBeGreaterThanOrEqual(2); // At least first and last name
        expect(nameParts.every((part) => part.length > 0)).toBe(true);
      }
    });

    it("generates imovel with positive area values", () => {
      const filled = fillFields(topology, 12345);

      expect(filled.imoveis.length).toBe(1);
      const imovel = filled.imoveis[0];

      expect(imovel.areaTotal).toBeGreaterThan(0);
      if (imovel.areaReservaLegal !== undefined) {
        expect(imovel.areaReservaLegal).toBeGreaterThan(0);
        expect(imovel.areaDemais).toBeDefined();
        expect(imovel.areaDemais!).toBeGreaterThan(0);
        expect(imovel.areaReservaLegal + imovel.areaDemais!).toBeCloseTo(imovel.areaTotal, 2);
      }
    });

    it("generates imovel with valid UF", () => {
      const filled = fillFields(topology, 12345);

      const imovel = filled.imoveis[0];
      const validUFs = [
        "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
        "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
        "SP", "SE", "TO",
      ];
      expect(validUFs).toContain(imovel.uf);
    });

    it("generates imovel with topologyId matching chain imovel", () => {
      const filled = fillFields(topology, 12345);

      expect(filled.imoveis[0].topologyId).toBe(topology.imovel.id);
    });

    it("generates chainId matching topology chainId", () => {
      const filled = fillFields(topology, 12345);

      expect(filled.chainId).toBe(topology.chainId);
    });

    it("generates 3-5 pessoas per chain", () => {
      const filled = fillFields(topology, 12345);

      expect(filled.pessoas.length).toBeGreaterThanOrEqual(3);
      expect(filled.pessoas.length).toBeLessThanOrEqual(5);
    });

    it("generates pessoas with unique topologyIds", () => {
      const filled = fillFields(topology, 12345);

      const topologyIds = filled.pessoas.map((p) => p.topologyId);
      const uniqueIds = new Set(topologyIds);
      expect(uniqueIds.size).toBe(topologyIds.length);
    });

    it("generates optional descricao for some documentos", () => {
      const filled = fillFields(topology, 12345);

      // Some documentos should have descricao, some should not
      const docsWithDescricao = filled.documentos.filter((d) => d.descricao !== undefined);
      expect(docsWithDescricao.length).toBeGreaterThan(0);
      expect(docsWithDescricao.length).toBeLessThan(filled.documentos.length);
    });

    it("handles linear chain topology", () => {
      const linearTopology = generateChainTopology(12345, 5, { shape: "linear" });
      const filled = fillFields(linearTopology, 12345);

      expect(filled.documentos.length).toBe(5);
      expect(filled.imoveis.length).toBe(1);
    });

    it("handles branching chain topology", () => {
      const branchingTopology = generateChainTopology(12345, 5, { shape: "branching" });
      const filled = fillFields(branchingTopology, 12345);

      expect(filled.documentos.length).toBe(5);
      expect(filled.imoveis.length).toBe(1);
    });

    it("handles merge chain topology", () => {
      const mergeTopology = generateChainTopology(12345, 5, { shape: "merge" });
      const filled = fillFields(mergeTopology, 12345);

      expect(filled.documentos.length).toBe(5);
      expect(filled.imoveis.length).toBe(1);
    });

    it("handles single-document chain", () => {
      const singleDocTopology = generateChainTopology(12345, 1);
      const filled = fillFields(singleDocTopology, 12345);

      expect(filled.documentos.length).toBe(1);
      expect(filled.imoveis.length).toBe(1);
    });

    it("generates imovel denominacao with capitalized words", () => {
      const filled = fillFields(topology, 12345);

      const imovel = filled.imoveis[0];
      // Check that each word starts with capital letter
      const words = imovel.denominacao.split(" ");
      for (const word of words) {
        expect(word[0]).toBe(word[0].toUpperCase());
      }
    });

    it("generates documento dates in ISO format (YYYY-MM-DD)", () => {
      const filled = fillFields(topology, 12345);

      for (const doc of filled.documentos) {
        expect(doc.data).toMatch(/^\d{4}-\d{2}-\d{2}$/);
        const date = new Date(doc.data);
        expect(date.toString()).not.toBe("Invalid Date");
      }
    });

    it("generates pessoa names with reasonable length", () => {
      const filled = fillFields(topology, 12345);

      for (const pessoa of filled.pessoas) {
        expect(pessoa.nome.length).toBeGreaterThan(2);
        expect(pessoa.nome.length).toBeLessThan(100);
      }
    });

    it("generates municipio name for imovel", () => {
      const filled = fillFields(topology, 12345);

      const imovel = filled.imoveis[0];
      expect(imovel.municipio.length).toBeGreaterThan(2);
      expect(imovel.municipio.length).toBeLessThan(100);
    });
  });

  describe("validateCpf", () => {
    it("rejects CPF with invalid check digits", () => {
      const invalidCpf = "123.456.789-00"; // Check digits are wrong
      expect(validateCpf(invalidCpf)).toBe(false);
    });

    it("rejects CPF with repeated digits", () => {
      expect(validateCpf("111.111.111-11")).toBe(false);
      expect(validateCpf("222.222.222-22")).toBe(false);
    });

    it("rejects malformed CPF", () => {
      expect(validateCpf("123.456.789")).toBe(false);
      expect(validateCpf("123.456.789-0")).toBe(false);
      expect(validateCpf("abc.def.ghi-jk")).toBe(false);
    });
  });

  describe("validateCnpj", () => {
    it("rejects CNPJ with invalid check digits", () => {
      const invalidCnpj = "12.345.678/0001-00"; // Check digits are wrong
      expect(validateCnpj(invalidCnpj)).toBe(false);
    });

    it("rejects CNPJ with repeated digits", () => {
      expect(validateCnpj("11.111.111/1111-11")).toBe(false);
      expect(validateCnpj("22.222.222/2222-22")).toBe(false);
    });

    it("rejects malformed CNPJ", () => {
      expect(validateCnpj("12.345.678/0001")).toBe(false);
      expect(validateCnpj("12.345.678/0001-0")).toBe(false);
      expect(validateCnpj("abc.def.ghi/jkl-mn")).toBe(false);
    });
  });
});
