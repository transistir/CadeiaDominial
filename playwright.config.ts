import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./packages/web/e2e",
  webServer: {
    command: "pnpm dev:web -- --host 0.0.0.0 --port 5173",
    url: "http://localhost:5173",
    reuseExistingServer: !process.env.CI
  },
  use: {
    baseURL: "http://localhost:5173"
  }
});
