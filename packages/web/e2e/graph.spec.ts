import { test, expect } from "@playwright/test";

test("graph page loads and renders core content", async ({ page }) => {
  await page.route("**/health", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true, timestamp: "2026-01-26T00:00:00.000Z" })
    });
  });

  await page.goto("/graph");

  await expect(page.getByTestId("graph-preview")).toBeVisible();
  await expect(page.getByText("M1234")).toBeVisible();
  await expect(page.getByText("T5678")).toBeVisible();
  await expect(page.getByText("Fim de Cadeia")).toBeVisible();
});
