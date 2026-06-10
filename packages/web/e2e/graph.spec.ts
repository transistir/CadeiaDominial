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

  // Check for structural elements using data-testid (not hardcoded fixture values)
  const documentoNodes = page.getByTestId("documento-node");
  await expect(documentoNodes).toHaveCount(2);

  const fimCadeiaNode = page.getByTestId("fim-cadeia-node");
  await expect(fimCadeiaNode).toHaveCount(1);

  const edgeLabels = page.getByTestId("origem-edge-label");
  await expect(edgeLabels).toHaveCount(2);

  // Verify edge labels have tipo attributes (structural check)
  await expect(page.locator('[data-testid="origem-edge-label"][data-tipo="matricula"]')).toHaveCount(1);
  await expect(page.locator('[data-testid="origem-edge-label"][data-tipo="fim_cadeia"]')).toHaveCount(1);
});
