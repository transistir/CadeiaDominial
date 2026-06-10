import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@cadeia/chain-topology": path.resolve(__dirname, "../../scripts/seed"),
    },
  },
  test: {
    exclude: ["**/e2e/**", "**/node_modules/**"],
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "lcov"],
      // Global thresholds kept at 80% because legacy files
      // (validateGraph.ts, topology-adapter.ts) have throw-path gaps
      // (Pitfall #15 in .hermes/plans/T-501.md). Per-file thresholds
      // enforce the T-501 spec gate ("100% unit test coverage on pure
      // functions") for the new pure-function files only.
      lines: 80,
      functions: 80,
      branches: 80,
      statements: 80,
      thresholds: {
        perFile: true,
        "src/graph/builder.ts": {
          lines: 100,
          functions: 100,
          branches: 100,
          statements: 100,
        },
        "src/graph/mock.ts": {
          lines: 100,
          functions: 100,
          branches: 100,
          statements: 100,
        },
      },
      exclude: ["**/e2e/**", "**/node_modules/**", "src/test/**"],
    },
  },
});