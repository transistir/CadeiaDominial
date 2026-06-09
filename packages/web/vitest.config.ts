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
      lines: 80,
      functions: 80,
      branches: 80,
      statements: 80,
      exclude: ["**/e2e/**", "**/node_modules/**", "src/test/**"],
    },
  },
});