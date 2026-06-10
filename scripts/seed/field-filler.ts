import { faker } from "@faker-js/faker";
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

/**
 * Generate a valid Brazilian CPF with correct check digits.
 *
 * CPF format: ddd.ddd.ddd-dd
 * The last two digits are check digits computed from the first nine.
 *
 * Algorithm:
 * 1. Generate 9 random digits (d1..d9)
 * 2. Compute first check digit (d10):
 *    - Multiply d1×10, d2×9, ..., d9×2
 *    - Sum the products
 *    - d10 = (sum × 10) % 11; if >= 10, use 0
 * 3. Compute second check digit (d11):
 *    - Multiply d1×11, d2×10, ..., d9×3, d10×2
 *    - Sum the products
 *    - d11 = (sum × 10) % 11; if >= 10, use 0
 *
 * @param invalid - If true, generate an INVALID CPF (for negative tests)
 */
export function generateCpf(invalid = false): string {
  // Generate 9 random digits
  const digits = Array.from({ length: 9 }, () => faker.number.int({ min: 0, max: 9 }));

  // Compute first check digit
  let sum = 0;
  for (let i = 0; i < 9; i++) {
    sum += digits[i] * (10 - i);
  }
  let digit10 = (sum * 10) % 11;
  if (digit10 >= 10) digit10 = 0;

  // Compute second check digit
  sum = 0;
  for (let i = 0; i < 9; i++) {
    sum += digits[i] * (11 - i);
  }
  sum += digit10 * 2;
  let digit11 = (sum * 10) % 11;
  if (digit11 >= 10) digit11 = 0;

  // If invalid flag is set, corrupt a data digit (not a check digit)
  if (invalid) {
    // Flip one of the first 9 digits to guarantee invalid CPF
    digits[0] = (digits[0] + 1) % 10;
  }

  const allDigits = [...digits, digit10, digit11];
  return `${allDigits.slice(0, 3).join("")}.${allDigits.slice(3, 6).join("")}.${allDigits.slice(6, 9).join("")}-${allDigits[9]}${allDigits[10]}`;
}

/**
 * Validate a CPF by verifying its check digits.
 * Returns true if the CPF has valid check digits, false otherwise.
 */
export function validateCpf(cpf: string): boolean {
  const digits = cpf.replace(/\D/g, "");
  if (digits.length !== 11) return false;

  const nums = digits.split("").map(Number);

  // Check if all digits are the same (invalid CPF pattern)
  if (nums.every((d) => d === nums[0])) return false;

  // Compute first check digit
  let sum = 0;
  for (let i = 0; i < 9; i++) {
    sum += nums[i] * (10 - i);
  }
  const digit10 = (sum * 10) % 11;
  const expectedDigit10 = digit10 >= 10 ? 0 : digit10;
  if (nums[9] !== expectedDigit10) return false;

  // Compute second check digit
  sum = 0;
  for (let i = 0; i < 9; i++) {
    sum += nums[i] * (11 - i);
  }
  sum += nums[9] * 2;
  const digit11 = (sum * 10) % 11;
  const expectedDigit11 = digit11 >= 10 ? 0 : digit11;
  if (nums[10] !== expectedDigit11) return false;

  return true;
}

/**
 * Generate a valid Brazilian CNPJ with correct check digits.
 *
 * CNPJ format: dd.ddd.ddd/dddd-dd
 * The last two digits are check digits computed from the first twelve.
 */
export function generateCnpj(): string {
  // Generate 12 random digits (first 8 are the registration number, next 4 are branch number)
  const baseDigits = Array.from({ length: 12 }, () => faker.number.int({ min: 0, max: 9 }));

  // Compute first check digit (d13)
  let sum = 0;
  const weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
  for (let i = 0; i < 12; i++) {
    sum += baseDigits[i] * weights1[i];
  }
  let remainder = sum % 11;
  const digit13 = remainder < 2 ? 0 : 11 - remainder;

  // Compute second check digit (d14)
  sum = 0;
  const weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
  const allButLast = [...baseDigits, digit13];
  for (let i = 0; i < 13; i++) {
    sum += allButLast[i] * weights2[i];
  }
  remainder = sum % 11;
  const digit14 = remainder < 2 ? 0 : 11 - remainder;

  const allDigits = [...baseDigits, digit13, digit14];
  return `${allDigits.slice(0, 2).join("")}.${allDigits.slice(2, 5).join("")}.${allDigits.slice(5, 8).join("")}/${allDigits.slice(8, 12).join("")}-${allDigits[12]}${allDigits[13]}`;
}

/**
 * Validate a CNPJ by verifying its check digits.
 * Returns true if the CNPJ has valid check digits, false otherwise.
 */
export function validateCnpj(cnpj: string): boolean {
  const digits = cnpj.replace(/\D/g, "");
  if (digits.length !== 14) return false;

  const nums = digits.split("").map(Number);

  // Check if all digits are the same (invalid CNPJ pattern)
  if (nums.every((d) => d === nums[0])) return false;

  // Compute first check digit
  let sum = 0;
  const weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
  for (let i = 0; i < 12; i++) {
    sum += nums[i] * weights1[i];
  }
  let remainder = sum % 11;
  const digit13 = remainder < 2 ? 0 : 11 - remainder;
  if (nums[12] !== digit13) return false;

  // Compute second check digit
  sum = 0;
  const weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
  for (let i = 0; i < 13; i++) {
    sum += nums[i] * weights2[i];
  }
  remainder = sum % 11;
  const digit14 = remainder < 2 ? 0 : 11 - remainder;
  if (nums[13] !== digit14) return false;

  return true;
}

/**
 * Filled documento with realistic field values.
 */
export interface FilledDocumento {
  /** The documento's topology ID (doc.id) */
  topologyId: string;
  /** Document number (e.g. "M-12345" or "T-67890") */
  numero: string;
  /** ISO date string (YYYY-MM-DD) */
  data: string;
  /** Optional description */
  descricao?: string;
}

/**
 * Filled pessoa (person or legal entity) with realistic field values.
 */
export interface FilledPessoa {
  /** The pessoa's topology ID (referenced entity id) */
  topologyId: string;
  /** Full name (person) or company name (legal entity) */
  nome: string;
  /** Valid CPF or CNPJ */
  cpfCnpj: string;
  /** "pf" for pessoa física (person), "pj" for pessoa jurídica (legal entity) */
  tipo: "pf" | "pj";
}

/**
 * Filled imovel (property) with realistic field values.
 */
export interface FilledImovel {
  /** The imovel's topology ID */
  topologyId: string;
  /** Property denomination (e.g. "Fazenda São José") */
  denominacao: string;
  /** Total area in hectares */
  areaTotal: number;
  /** Legal reserve area in hectares (optional) */
  areaReservaLegal?: number;
  /** Remaining area in hectares (optional) */
  areaDemais?: number;
  /** Municipality name */
  municipio: string;
  /** State abbreviation (UF) */
  uf: string;
}

/**
 * Filled chain with all entities enriched with realistic field values.
 */
export interface FilledChain {
  /** Chain ID from topology */
  chainId: string;
  /** Filled documentos */
  documentos: FilledDocumento[];
  /** Filled pessoas (persons and legal entities) */
  pessoas: FilledPessoa[];
  /** Filled imoveis (properties) */
  imoveis: FilledImovel[];
}

/**
 * Generate a random date within the last 10 years.
 */
function randomDate(): Date {
  const end = new Date();
  const start = new Date();
  start.setFullYear(end.getFullYear() - 10);
  return faker.date.between({ from: start, to: end });
}

/**
 * Add a random number of days (30-365) to a date.
 */
function addDays(date: Date, days: number): Date {
  const result = new Date(date);
  result.setDate(result.getDate() + days);
  return result;
}

/**
 * Format a Date as ISO string (YYYY-MM-DD).
 */
function formatDate(date: Date): string {
  return date.toISOString().split("T")[0];
}

/**
 * Get a Brazilian state abbreviation (UF).
 */
function randomUf(): string {
  const ufs = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
  ];
  return faker.helpers.arrayElement(ufs);
}


/**
 * Fill non-structural fields in a topology graph with realistic values.
 *
 * This function takes a TopologyGraph (from chain-topology.ts) and enriches
 * it with realistic field values for documents, persons, and properties using
 * @faker-js/faker with Portuguese locale.
 *
 * @param topology - The topology graph to fill
 * @param seed - Optional seed for deterministic output. If not provided,
 *               derived from the chainId hash.
 * @returns Filled chain with all entities enriched with realistic values
 */
export function fillFields(topology: TopologyGraph, seed?: number): FilledChain {
  // Derive seed from chainId if not provided
  const actualSeed = seed ?? hashString(topology.chainId);

  // Seed faker for deterministic output
  faker.seed(actualSeed);

  const documentos: FilledDocumento[] = [];
  const pessoas: FilledPessoa[] = [];
  const imoveis: FilledImovel[] = [];

  // Type-specific sequential counters (no gaps)
  let matriculaCounter = 1;
  let transcricaoCounter = 1;

  // Generate documentos with monotonically increasing dates
  let currentDate = randomDate();
  for (let i = 0; i < topology.documentos.length; i++) {
    const doc = topology.documentos[i];

    // Generate sequential number based on tipo
    const numero = doc.tipo === "matricula"
      ? `M-${String(matriculaCounter++).padStart(5, "0")}`
      : `T-${String(transcricaoCounter++).padStart(5, "0")}`;

    const data = formatDate(currentDate);

    // Randomly decide whether to include a description (30% chance)
    const descricao = faker.datatype.boolean({ probability: 0.3 })
      ? faker.lorem.sentence({ min: 5, max: 15 })
      : undefined;

    documentos.push({
      topologyId: doc.id,
      numero,
      data,
      descricao,
    });

    // Move to next date (30-365 days later)
    const daysToAdd = faker.number.int({ min: 30, max: 365 });
    currentDate = addDays(currentDate, daysToAdd);
  }

  // Generate pessoas (3-5 per chain)
  const pessoaCount = faker.number.int({ min: 3, max: 5 });
  for (let i = 0; i < pessoaCount; i++) {
    const isPessoaFisica = faker.datatype.boolean({ probability: 0.7 }); // 70% PF, 30% PJ

    if (isPessoaFisica) {
      pessoas.push({
        topologyId: `pessoa-pf-${i + 1}`,
        nome: faker.person.fullName(),
        cpfCnpj: generateCpf(),
        tipo: "pf",
      });
    } else {
      pessoas.push({
        topologyId: `pessoa-pj-${i + 1}`,
        nome: faker.company.name(),
        cpfCnpj: generateCnpj(),
        tipo: "pj",
      });
    }
  }

  // Generate imovel (exactly 1 per chain per S-3)
  const areaTotal = faker.number.float({ min: 10, max: 10000, fractionDigits: 2 });
  const hasReservaLegal = faker.datatype.boolean({ probability: 0.8 });

  let areaReservaLegal: number | undefined;
  let areaDemais: number | undefined;

  if (hasReservaLegal) {
    // Legal reserve is 20-35% of total area
    const reservaPercentage = faker.number.float({ min: 0.20, max: 0.35, fractionDigits: 2 });
    const rawReserva = areaTotal * reservaPercentage;
    areaReservaLegal = Math.round(rawReserva * 100) / 100;
    // areaDemais is the remainder, rounded once to avoid float precision issues
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
    uf: randomUf(),
  });

  return {
    chainId: topology.chainId,
    documentos,
    pessoas,
    imoveis,
  };
}
