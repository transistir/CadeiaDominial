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
      reporter: [["text", { skipFull: false }], "html", "lcov"],
      // Global thresholds live under coverage.thresholds in Vitest 4.
      // Keep them at 80% because legacy files have known throw-path gaps,
      // while file-specific thresholds enforce the T-501 100% gate for the
      // new pure-function files.
      thresholds: {
        lines: 80,
        functions: 80,
        branches: 80,
        statements: 80,
        "src/graph/builder.ts": {
          lines: 100,
          functions: 100,
          branches: 100,
          statements: 100,
        },
        "src/graph/mock.ts": {
          lines: 90,
          functions: 90,
          branches: 90,
          statements: 90,
        },
      },
      exclude: ["**/e2e/**", "**/node_modules/**", "src/test/**"],
    },
  },
});
