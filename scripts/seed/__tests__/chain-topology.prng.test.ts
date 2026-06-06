import { describe, it, expect } from "vitest";
import {
  hashSeed,
  createRng,
  pick,
  pickIndex,
  shuffle,
  intInRange,
} from "../chain-topology.prng";

describe("chain-topology.prng", () => {
  describe("hashSeed", () => {
    it("returns a 32-bit unsigned int for a number seed", () => {
      const h = hashSeed(12345);
      expect(h).toBe(12345);
      expect(h).toBeGreaterThanOrEqual(0);
      expect(h).toBeLessThan(2 ** 32);
    });

    it("normalizes negative numbers to 32-bit unsigned", () => {
      expect(hashSeed(-1)).toBe(0xffffffff);
      expect(hashSeed(-2)).toBe(0xfffffffe);
    });

    it("returns deterministic hash for string seeds", () => {
      expect(hashSeed("hello")).toBe(hashSeed("hello"));
    });

    it("returns different hashes for different strings", () => {
      expect(hashSeed("hello")).not.toBe(hashSeed("world"));
    });

    it("returns 0 for non-finite numbers", () => {
      expect(hashSeed(NaN)).toBe(0);
      expect(hashSeed(Infinity)).toBe(0);
      expect(hashSeed(-Infinity)).toBe(0);
    });

    it("handles empty string", () => {
      const h = hashSeed("");
      expect(h).toBeGreaterThanOrEqual(0);
      expect(h).toBeLessThan(2 ** 32);
    });
  });

  describe("createRng", () => {
    it("produces deterministic sequence for same seed", () => {
      const r1 = createRng(42);
      const r2 = createRng(42);
      for (let i = 0; i < 100; i++) {
        expect(r1()).toBe(r2());
      }
    });

    it("produces deterministic sequence for same string seed", () => {
      const r1 = createRng("seed-string");
      const r2 = createRng("seed-string");
      for (let i = 0; i < 100; i++) {
        expect(r1()).toBe(r2());
      }
    });

    it("produces different sequences for different seeds", () => {
      const r1 = createRng(1);
      const r2 = createRng(2);
      const seq1 = Array.from({ length: 10 }, () => r1());
      const seq2 = Array.from({ length: 10 }, () => r2());
      expect(seq1).not.toEqual(seq2);
    });

    it("produces values in [0, 1)", () => {
      const rng = createRng(0);
      for (let i = 0; i < 1000; i++) {
        const v = rng();
        expect(v).toBeGreaterThanOrEqual(0);
        expect(v).toBeLessThan(1);
      }
    });
  });

  describe("pick", () => {
    it("returns an element from the array", () => {
      const rng = createRng(0);
      const arr = [1, 2, 3, 4, 5];
      for (let i = 0; i < 100; i++) {
        expect(arr).toContain(pick(arr, rng));
      }
    });

    it("throws on empty array", () => {
      const rng = createRng(0);
      expect(() => pick([], rng)).toThrow(RangeError);
    });

    it("is deterministic for a seeded rng", () => {
      const rng1 = createRng(7);
      const rng2 = createRng(7);
      const arr = ["a", "b", "c", "d", "e"];
      for (let i = 0; i < 20; i++) {
        expect(pick(arr, rng1)).toBe(pick(arr, rng2));
      }
    });
  });

  describe("pickIndex", () => {
    it("returns an index in [0, n)", () => {
      const rng = createRng(0);
      for (let i = 0; i < 1000; i++) {
        const idx = pickIndex(5, rng);
        expect(idx).toBeGreaterThanOrEqual(0);
        expect(idx).toBeLessThan(5);
        expect(Number.isInteger(idx)).toBe(true);
      }
    });

    it("throws for non-positive n", () => {
      const rng = createRng(0);
      expect(() => pickIndex(0, rng)).toThrow(RangeError);
      expect(() => pickIndex(-1, rng)).toThrow(RangeError);
    });

    it("throws for non-integer n", () => {
      const rng = createRng(0);
      expect(() => pickIndex(1.5, rng)).toThrow(RangeError);
    });
  });

  describe("shuffle", () => {
    it("returns a new array of the same length", () => {
      const rng = createRng(0);
      const arr = [1, 2, 3, 4, 5];
      const shuffled = shuffle(arr, rng);
      expect(shuffled).toHaveLength(arr.length);
      expect(shuffled).not.toBe(arr);
    });

    it("preserves all elements (multiset equality)", () => {
      const rng = createRng(0);
      const arr = [1, 2, 3, 4, 5];
      const shuffled = shuffle(arr, rng);
      expect([...shuffled].sort()).toEqual([...arr].sort());
    });

    it("is deterministic for a seeded rng", () => {
      const arr = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
      const s1 = shuffle(arr, createRng(42));
      const s2 = shuffle(arr, createRng(42));
      expect(s1).toEqual(s2);
    });

    it("does not mutate the input", () => {
      const rng = createRng(0);
      const arr = [1, 2, 3, 4, 5];
      const copy = arr.slice();
      shuffle(arr, rng);
      expect(arr).toEqual(copy);
    });

    it("handles empty and single-element arrays", () => {
      const rng = createRng(0);
      expect(shuffle([], rng)).toEqual([]);
      expect(shuffle([42], rng)).toEqual([42]);
    });
  });

  describe("intInRange", () => {
    it("returns an integer in [min, max]", () => {
      const rng = createRng(0);
      for (let i = 0; i < 1000; i++) {
        const v = intInRange(3, 7, rng);
        expect(v).toBeGreaterThanOrEqual(3);
        expect(v).toBeLessThanOrEqual(7);
        expect(Number.isInteger(v)).toBe(true);
      }
    });

    it("covers the full range over many samples", () => {
      const rng = createRng(123);
      const seen = new Set<number>();
      for (let i = 0; i < 1000; i++) {
        seen.add(intInRange(0, 4, rng));
      }
      expect(seen.size).toBe(5);
    });

    it("returns min when min === max", () => {
      const rng = createRng(0);
      expect(intInRange(5, 5, rng)).toBe(5);
    });

    it("throws when min > max", () => {
      const rng = createRng(0);
      expect(() => intInRange(10, 5, rng)).toThrow(RangeError);
    });

    it("throws for non-integer bounds", () => {
      const rng = createRng(0);
      expect(() => intInRange(1.5, 5, rng)).toThrow(RangeError);
      expect(() => intInRange(1, 5.5, rng)).toThrow(RangeError);
    });
  });
});
