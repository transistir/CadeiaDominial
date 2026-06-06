/**
 * Deterministic random helpers for the chain-topology generator.
 *
 * PRNG choice: mulberry32.
 *   - 32-bit state, period 2^32, one-line state update.
 *   - Fast, well-distributed for non-cryptographic use (topology/type
 *     selection is the only consumer).
 *   - Seeded via a 32-bit unsigned int; string seeds are folded into one
 *     via hashSeed() (FNV-1a) before being passed in.
 *
 * All helpers are pure: they take an `rng` function and return values
 * without mutating any input. The PRNG itself is a closure over a single
 * `let a`, so two `createRng(seed)` calls with the same seed produce
 * byte-identical sequences.
 */

/** Hash a string or number seed into a 32-bit unsigned int. */
export function hashSeed(seed: string | number): number {
  if (typeof seed === "number") {
    if (!Number.isFinite(seed)) return 0;
    return seed >>> 0;
  }
  // FNV-1a 32-bit for strings.
  let h = 2166136261 >>> 0;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h;
}

/** Create a PRNG function from a string or number seed. */
export function createRng(seed: string | number): () => number {
  return mulberry32(hashSeed(seed));
}

function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Uniform random pick from a non-empty array. */
export function pick<T>(arr: readonly T[], rng: () => number): T {
  if (arr.length === 0) throw new RangeError("pick: empty array");
  return arr[pickIndex(arr.length, rng)];
}

/** Uniform random integer index in [0, n). */
export function pickIndex(n: number, rng: () => number): number {
  if (!Number.isInteger(n) || n <= 0) {
    throw new RangeError(`pickIndex: n must be a positive integer, got ${n}`);
  }
  return Math.floor(rng() * n);
}

/** Fisher-Yates shuffle; returns a new array, does not mutate the input. */
export function shuffle<T>(arr: readonly T[], rng: () => number): T[] {
  const out = arr.slice();
  for (let i = out.length - 1; i > 0; i--) {
    const j = pickIndex(i + 1, rng);
    const tmp = out[i]!;
    out[i] = out[j]!;
    out[j] = tmp;
  }
  return out;
}

/** Uniform random integer in [min, max], inclusive on both ends. */
export function intInRange(min: number, max: number, rng: () => number): number {
  if (!Number.isInteger(min) || !Number.isInteger(max)) {
    throw new RangeError("intInRange: min and max must be integers");
  }
  if (min > max) {
    throw new RangeError(`intInRange: min (${min}) > max (${max})`);
  }
  if (min === max) return min;
  return min + pickIndex(max - min + 1, rng);
}
