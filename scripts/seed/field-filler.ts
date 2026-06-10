import { Faker, pt_BR, type Faker as FakerType } from "@faker-js/faker";
import type {
  TopologyGraph,
} from "./chain-topology.js";

/**
 * Simple hash of a string to a number. Used to derive a deterministic seed
 * from the chainId when no explicit seed is provided.
 */
function hashString(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return Math.abs(hash);
}

// ── Fixed date range for deterministic cross-run output ──
// Anchor to a fixed window (2010–2020) instead of wall-clock time,
// so that the same seed always produces the same output regardless
// of when the process runs.  Greptile P1.
const FIXED_DATE_START = new Date("2010-01-01");
const FIXED_DATE_END = new Date("2020-12-31");

// ── CPF helpers (algorithm — faker-independent) ──

function computeCpfCheckDigits(digits: number[]): [number, number] {
  let sum = 0;
  for (let i = 0; i < 9; i++) sum += digits[i] * (10 - i);
  let d10 = (sum * 10) % 11;
  if (d10 >= 10) d10 = 0;

  sum = 0;
  for (let i = 0; i < 9; i++) sum += digits[i] * (11 - i);
  sum += d10 * 2;
  let d11 = (sum * 10) % 11;
  if (d11 >= 10) d11 = 0;

  return [d10, d11];
}

function generateCpfWithFaker(faker: FakerType, invalid = false): string {
  const digits = Array.from({ length: 9 }, () => faker.number.int({ min: 0, max: 9 }));
  const [d10, d11] = computeCpfCheckDigits(digits);

  if (invalid) {
    digits[0] = (digits[0] + 1) % 10;
  }

  const all = [...digits, d10, d11];
  return `${all.slice(0, 3).join("")}.${all.slice(3, 6).join("")}.${all.slice(6, 9).join("")}-${all[9]}${all[10]}`;
}

/**
 * Generate a valid Brazilian CPF with correct check digits.
 * Uses a dedicated faker instance for isolation — see generateCpfIsolated.
 */
export function generateCpf(invalid = false): string {
  return generateCpfWithFaker(new Faker({ locale: pt_BR }), invalid);
}

/**
 * Validate a CPF by verifying its check digits.
 * Returns true if the CPF has valid check digits, false otherwise.
 */
export function validateCpf(cpf: string): boolean {
  const digits = cpf.replace(/\D/g, "");
  if (digits.length !== 11) return false;

  const nums = digits.split("").map(Number);

  // Reject CPFs with all identical digits (e.g., 111.111.111-11)
  if (nums.every((d) => d === nums[0])) return false;

  const [expectedD10, expectedD11] = computeCpfCheckDigits(nums.slice(0, 9));
  return nums[9] === expectedD10 && nums[10] === expectedD11;
}

// ── CNPJ helpers (algorithm — faker-independent) ──

const CNPJ_WEIGHTS1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
const CNPJ_WEIGHTS2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];

function computeCnpjCheckDigits(digits: number[]): [number, number] {
  let sum = 0;
  for (let i = 0; i < 12; i++) sum += digits[i] * CNPJ_WEIGHTS1[i];
  const rem1 = sum % 11;
  const d13 = rem1 < 2 ? 0 : 11 - rem1;

  sum = 0;
  for (let i = 0; i < 12; i++) sum += digits[i] * CNPJ_WEIGHTS2[i];
  sum += d13 * CNPJ_WEIGHTS2[12];
  const rem2 = sum % 11;
  const d14 = rem2 < 2 ? 0 : 11 - rem2;

  return [d13, d14];
}

function generateCnpjWithFaker(faker: FakerType): string {
  const base = Array.from({ length: 12 }, () => faker.number.int({ min: 0, max: 9 }));
  const [d13, d14] = computeCnpjCheckDigits(base);
  const all = [...base, d13, d14];
  return `${all.slice(0, 2).join("")}.${all.slice(2, 5).join("")}.${all.slice(5, 8).join("")}/${all.slice(8, 12).join("")}-${all[12]}${all[13]}`;
}

/**
 * Generate a valid Brazilian CNPJ with correct check digits.
 * Uses a dedicated faker instance for isolation.
 */
export function generateCnpj(): string {
  return generateCnpjWithFaker(new Faker({ locale: pt_BR }));
}

/**
 * Validate a CNPJ by verifying its check digits.
 * Returns true if the CNPJ has valid check digits, false otherwise.
 */
export function validateCnpj(cnpj: string): boolean {
  const digits = cnpj.replace(/\D/g, "");
  if (digits.length !== 14) return false;

  const nums = digits.split("").map(Number);

  if (nums.every((d) => d === nums[0])) return false;

  const [expectedD13, expectedD14] = computeCnpjCheckDigits(nums.slice(0, 12));
  return nums[12] === expectedD13 && nums[13] === expectedD14;
}

// ── Filled types ──

export interface FilledDocumento {
  topologyId: string;
  numero: string;
  data: string;
  descricao?: string;
}

export interface FilledPessoa {
  topologyId: string;
  nome: string;
  cpfCnpj: string;
  tipo: "pf" | "pj";
}

export interface FilledImovel {
  topologyId: string;
  denominacao: string;
  areaTotal: number;
  areaReservaLegal?: number;
  areaDemais?: number;
  municipio: string;
  uf: string;
}

export interface FilledChain {
  chainId: string;
  documentos: FilledDocumento[];
  pessoas: FilledPessoa[];
  imoveis: FilledImovel[];
}

// ── Internal helpers (all accept a local faker for isolation) ──

function randomDate(faker: FakerType): Date {
  return faker.date.between({ from: FIXED_DATE_START, to: FIXED_DATE_END });
}

function addDays(date: Date, days: number): Date {
  const result = new Date(date);
  result.setDate(result.getDate() + days);
  return result;
}

function formatDate(date: Date): string {
  return date.toISOString().split("T")[0];
}

const BRAZILIAN_UFS = [
  "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
  "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
  "SP", "SE", "TO",
];

function randomUf(faker: FakerType): string {
  return faker.helpers.arrayElement(BRAZILIAN_UFS);
}

/**
 * Fill non-structural fields in a topology graph with realistic values.
 *
 * Uses a **local** Faker instance (not the global singleton) so that
 * concurrent calls (e.g. parallel Vitest files) cannot corrupt each
 * other's PRNG streams.  Greptile P3.
 *
 * The date range is anchored to a fixed 2010–2020 window so that
 * the same seed produces identical output across runs.  Greptile P1.
 *
 * @param topology - The topology graph to fill
 * @param seed - Optional seed for deterministic output. If not provided,
 *               derived from the chainId hash.
 * @returns Filled chain with all entities enriched with realistic values
 */
export function fillFields(topology: TopologyGraph, seed?: number): FilledChain {
  const actualSeed = seed ?? hashString(topology.chainId);

  // Local faker instance — isolates PRNG state from concurrent callers
  const faker = new Faker({ locale: pt_BR });
  faker.seed(actualSeed);

  const documentos: FilledDocumento[] = [];
  const pessoas: FilledPessoa[] = [];
  const imoveis: FilledImovel[] = [];

  let matriculaCounter = 1;
  let transcricaoCounter = 1;

  let currentDate = randomDate(faker);
  for (let i = 0; i < topology.documentos.length; i++) {
    const doc = topology.documentos[i];

    const numero = doc.tipo === "matricula"
      ? `M-${String(matriculaCounter++).padStart(5, "0")}`
      : `T-${String(transcricaoCounter++).padStart(5, "0")}`;

    const data = formatDate(currentDate);

    const descricao = faker.datatype.boolean({ probability: 0.3 })
      ? faker.lorem.sentence({ min: 5, max: 15 })
      : undefined;

    documentos.push({
      topologyId: doc.id,
      numero,
      data,
      descricao,
    });

    const daysToAdd = faker.number.int({ min: 30, max: 365 });
    currentDate = addDays(currentDate, daysToAdd);
  }

  const pessoaCount = faker.number.int({ min: 3, max: 5 });
  for (let i = 0; i < pessoaCount; i++) {
    const isPessoaFisica = faker.datatype.boolean({ probability: 0.7 });

    if (isPessoaFisica) {
      pessoas.push({
        topologyId: `pessoa-pf-${i + 1}`,
        nome: faker.person.fullName(),
        cpfCnpj: generateCpfWithFaker(faker),
        tipo: "pf",
      });
    } else {
      pessoas.push({
        topologyId: `pessoa-pj-${i + 1}`,
        nome: faker.company.name(),
        cpfCnpj: generateCnpjWithFaker(faker),
        tipo: "pj",
      });
    }
  }

  const areaTotal = faker.number.float({ min: 10, max: 10000, fractionDigits: 2 });
  const hasReservaLegal = faker.datatype.boolean({ probability: 0.8 });

  let areaReservaLegal: number | undefined;
  let areaDemais: number | undefined;

  if (hasReservaLegal) {
    const reservaPercentage = faker.number.float({ min: 0.20, max: 0.35, fractionDigits: 2 });
    const rawReserva = areaTotal * reservaPercentage;
    areaReservaLegal = Math.round(rawReserva * 100) / 100;
    areaDemais = +(areaTotal - areaReservaLegal).toFixed(2);
  }

  imoveis.push({
    topologyId: topology.imovel.id,
    denominacao: faker.lorem.words({ min: 2, max: 4 }).split(" ").map((word) =>
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(" "),
    areaTotal,
    areaReservaLegal,
    areaDemais,
    municipio: faker.location.city(),
    uf: randomUf(faker),
  });

  return {
    chainId: topology.chainId,
    documentos,
    pessoas,
    imoveis,
  };
}
