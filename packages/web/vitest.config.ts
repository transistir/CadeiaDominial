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
    environment: "jsdom",
    globals: true,
  },
});