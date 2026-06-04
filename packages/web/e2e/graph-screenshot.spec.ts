import { test, expect } from "@playwright/test";
import { mkdir, stat } from "fs/promises";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

test("graph preview renders and screenshot is saved", async ({ page }) => {
  // Route health check to avoid API dependency
  await page.route("**/health", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true, timestamp: "2026-01-26T00:00:00.000Z" })
    });
  });

  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto("/graph");

  // Wait for graph preview to be visible
  const graphPreview = page.getByTestId("graph-preview");
  await expect(graphPreview).toBeVisible();

  // Wait for React Flow nodes to render
  const nodes = page.locator(".react-flow__node");
  await expect(nodes).toHaveCount(3);
  await expect(nodes.first()).toBeVisible();

  // Ensure screenshots directory exists (relative to repo root)
  const __dirname = dirname(fileURLToPath(import.meta.url));
  const screenshotsDir = join(__dirname, "..", "..", "..", "screenshots");
  await mkdir(screenshotsDir, { recursive: true });

  // Take screenshot
  const screenshotPath = join(screenshotsDir, "basic-graph.png");
  await page.screenshot({
    path: screenshotPath,
    fullPage: false
  });

  // Verify screenshot file exists and is non-empty
  const fileStats = await stat(screenshotPath);
  expect(fileStats.size).toBeGreaterThan(0);
});
