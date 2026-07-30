import {
  generateChainTopology,
  type TopologyGraph,
} from "./chain-topology.js";
import { fillFields, type FilledChain } from "./field-filler.js";

export const DEFAULT_CHAIN_COUNT = 50;
export const LANCAMENTOS_PER_CHAIN = 10;

/** How many documents to request per shape so the topology contains
 *  at least LANCAMENTOS_PER_CHAIN lancamentos. */
function getDocumentCount(shape: SeedShape): number {
  switch (shape) {
    case "linear":
      // n docs → n-1 lancamentos; n-1 >= target ⇒ n >= target + 1
      return LANCAMENTOS_PER_CHAIN + 1;
    case "branching":
      // prefixLen docs → prefixLen-1 lancs, then 2 branch lancs = prefixLen+1 total
      // prefixLen = n-2, so n-1 lancs. n-1 >= target ⇒ n >= target + 1
      return LANCAMENTOS_PER_CHAIN + 1;
    case "merge":
      // 1 merge lanc + (n-3) suffix lancs = n - 2 total
      // n-2 >= target ⇒ n >= target + 2
      return LANCAMENTOS_PER_CHAIN + 2;
  }
}

export type SeedShape = "linear" | "branching" | "merge";

export interface SeedOptions {
  count: number;
  seed: string;
  shape?: SeedShape;
}

export interface GeneratedSeedChain {
  index: number;
  seed: string;
  shape: SeedShape;
  topology: TopologyGraph;
  filled: FilledChain;
}

/**
 * Simple stable string-to-32-bit hash function.
 * Uses a well-tested integer mixing approach.
 */
function hashString(str: string): number {
  let hash = 5381; // djb2 initial value
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = Math.imul(33, hash) + char; // hash * 33 + char
    hash = hash | 0; // Force to 32-bit integer
  }
  // Final mixing for better distribution
  hash = Math.imul(hash ^ (hash >>> 16), 2246822507) >>> 0;
  hash = Math.imul(hash ^ (hash >>> 13), 3266489909) >>> 0;
  return (hash ^ (hash >>> 16)) >>> 0;
}

/**
 * Derive a deterministic seed for a specific chain from a run seed and index.
 * Uses a stable hash function to ensure reproducibility.
 */
export function deriveChainSeed(runSeed: string, index: number): string {
  const input = `${runSeed}:chain:${index}`;
  return hashString(input).toString();
}

/**
 * Choose a chain shape deterministically based on run seed and index.
 * Distribution: 10% linear, 60% branching, 30% merge.
 */
export function chooseShape(runSeed: string, index: number): SeedShape {
  const input = `${runSeed}:shape:${index}`;
  const hash = hashString(input);
  const roll = hash / 0x100000000; // Normalize to [0, 1) using 2^32

  if (roll < 0.10) {
    return "linear";
  } else if (roll < 0.70) {
    return "branching";
  } else {
    return "merge";
  }
}

/**
 * Parse command-line arguments for seed generation.
 * Supports both space and equals formats: --count 50, --count=50
 */
export function parseSeedArgs(
  argv: readonly string[],
  randomSeed?: () => string,
): SeedOptions {
  const options: SeedOptions = {
    count: DEFAULT_CHAIN_COUNT,
    seed: "", // resolved after parsing; empty triggers lazy default
  };

  let i = 0;
  while (i < argv.length) {
    const arg = argv[i];

    if (arg === "--count") {
      i++;
      if (i >= argv.length) {
        throw new Error("--count requires a value");
      }
      const countStr = argv[i];
      const count = Number(countStr);
      if (
        Number.isNaN(count) ||
        !Number.isFinite(count) ||
        !Number.isInteger(count) ||
        count < 1
      ) {
        throw new Error(
          `--count must be a positive integer, got "${countStr}"`,
        );
      }
      options.count = count;
    } else if (arg === "--count=") {
      throw new Error("--count= requires a value");
    } else if (arg.startsWith("--count=")) {
      const countStr = arg.slice(8);
      const count = Number(countStr);
      if (
        Number.isNaN(count) ||
        !Number.isFinite(count) ||
        !Number.isInteger(count) ||
        count < 1
      ) {
        throw new Error(
          `--count must be a positive integer, got "${countStr}"`,
        );
      }
      options.count = count;
    } else if (arg === "--seed") {
      i++;
      if (i >= argv.length) {
        throw new Error("--seed requires a value");
      }
      options.seed = argv[i];
    } else if (arg === "--seed=") {
      throw new Error("--seed= requires a value");
    } else if (arg.startsWith("--seed=")) {
      options.seed = arg.slice(7);
    } else if (arg === "--shape") {
      i++;
      if (i >= argv.length) {
        throw new Error("--shape requires a value");
      }
      const shape = argv[i];
      if (shape !== "linear" && shape !== "branching" && shape !== "merge") {
        throw new Error(
          `--shape must be "linear", "branching", or "merge", got "${shape}"`,
        );
      }
      options.shape = shape;
    } else if (arg === "--shape=") {
      throw new Error("--shape= requires a value");
    } else if (arg.startsWith("--shape=")) {
      const shape = arg.slice(8);
      if (shape !== "linear" && shape !== "branching" && shape !== "merge") {
        throw new Error(
          `--shape must be "linear", "branching", or "merge", got "${shape}"`,
        );
      }
      options.shape = shape;
    } else if (arg.startsWith("--")) {
      throw new Error(`Unknown flag: ${arg}`);
    } else {
      throw new Error(`Unexpected argument: ${arg}`);
    }
    i++;
  }

  // Lazy default: resolve seed after parsing so explicit --seed wins
  if (!options.seed) {
    options.seed = (randomSeed ?? (() => crypto.randomUUID()))();
  }

  return options;
}

/**
 * Generate a batch of seed chains with deterministic topology and filled fields.
 * Validates uniqueness and consistency before returning.
 */
export function generateSeedChains(options: SeedOptions): GeneratedSeedChain[] {
  const chains: GeneratedSeedChain[] = [];
  const chainIds = new Set<string>();

  for (let i = 0; i < options.count; i++) {
    const chainSeed = deriveChainSeed(options.seed, i);
    const shape = options.shape ?? chooseShape(options.seed, i);
    const seedNum = Number.parseInt(chainSeed, 10);

    const topology = generateChainTopology(
      seedNum,
      getDocumentCount(shape),
      { shape },
    );
    const filled = fillFields(topology, seedNum);

    // Validate uniqueness
    if (chainIds.has(topology.chainId)) {
      throw new Error(
        `Duplicate chainId generated: ${topology.chainId}`,
      );
    }
    chainIds.add(topology.chainId);

    // Validate symmetry
    if (topology.chainId !== filled.chainId) {
      throw new Error(
        `Chain ID mismatch: topology.chainId="${topology.chainId}" != filled.chainId="${filled.chainId}"`,
      );
    }

    chains.push({
      index: i,
      seed: chainSeed,
      shape,
      topology,
      filled,
    });
  }

  return chains;
}
