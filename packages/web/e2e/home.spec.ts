import { test, expect } from "@playwright/test";

test("home page renders hero content", async ({ page }) => {
  await page.route("**/health", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true, timestamp: "2026-01-26T00:00:00.000Z" })
    });
  });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: /track land records/i })).toBeVisible();
});
