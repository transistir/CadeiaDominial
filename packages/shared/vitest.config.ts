import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    globals: true,
    // `pool: "threads"` works around a vitest v4 fork-mode failure
    // (`ENOENT mkdir /tmp/.../ssr`) seen in restricted sandboxes that
    // disable temp-dir creation. Threads uses Web Workers in-process
    // and is faster to start than forks. CI works in both modes; this
    // is a defensive setting for cross-environment portability.
    pool: "threads",
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "lcov"],
      lines: 80,
      functions: 80,
      branches: 80,
      statements: 80,
      exclude: ["node_modules/**"]
    }
  }
});
