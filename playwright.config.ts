import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./packages/web/e2e",
  use: {
    baseURL: "http://localhost:5173"
  }
});
