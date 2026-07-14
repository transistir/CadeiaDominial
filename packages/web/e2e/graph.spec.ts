import { test, expect } from "@playwright/test";

test("graph page loads with complex mock by default", async ({ page }) => {
  await page.route("**/health", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true, timestamp: "2026-01-26T00:00:00.000Z" })
    });
  });

  await page.goto("/graph?mock=1");

  await expect(page.getByTestId("graph-view")).toBeVisible();

  const documentoNodes = page.getByTestId("documento-node");
  await expect(documentoNodes).toHaveCount(16);

  const fimCadeiaNodes = page.getByTestId("fim-cadeia-node");
  await expect(fimCadeiaNodes).toHaveCount(5);
});

test("mock shape selector switches between shapes", async ({ page }) => {
  await page.route("**/health", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true, timestamp: "2026-01-26T00:00:00.000Z" })
    });
  });

  await page.goto("/graph?mock=1");

  const select = page.getByTestId("mock-shape-select");
  await expect(select).toBeVisible();

  await select.selectOption("linear");
  await expect(page.getByTestId("documento-node")).toHaveCount(5);
  await expect(page.getByTestId("fim-cadeia-node")).toHaveCount(1);

  await select.selectOption("branching");
  await expect(page.getByTestId("documento-node")).toHaveCount(4);
  await expect(page.getByTestId("fim-cadeia-node")).toHaveCount(2);

  await select.selectOption("merge");
  await expect(page.getByTestId("documento-node")).toHaveCount(3);
  await expect(page.getByTestId("fim-cadeia-node")).toHaveCount(1);

  await select.selectOption("complex");
  await expect(page.getByTestId("documento-node")).toHaveCount(16);
  await expect(page.getByTestId("fim-cadeia-node")).toHaveCount(5);
});

test("node click opens detail panel", async ({ page }) => {
  await page.route("**/health", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true, timestamp: "2026-01-26T00:00:00.000Z" })
    });
  });

  await page.goto("/graph?mock=1");

  const panel = page.getByTestId("detail-panel");
  await expect(panel).toHaveClass(/graph-view__panel--closed/);

  const select = page.getByTestId("mock-shape-select");
  await select.selectOption("linear");

  const firstDocNode = page.getByTestId("documento-node").first();
  await expect(firstDocNode).toBeVisible();
  await firstDocNode.click();

  await expect(panel).toHaveClass(/graph-view__panel--open/);
  await expect(panel.getByText("Número")).toBeVisible();
  await expect(panel.getByText("Tipo")).toBeVisible();
  await expect(panel.getByText("Cartório")).toBeVisible();
  await expect(panel.getByText("Data")).toBeVisible();

  const closeButton = page.getByTestId("detail-panel-close");
  await closeButton.click();

  await expect(panel).toHaveClass(/graph-view__panel--closed/);
});

test("minimap and controls are rendered", async ({ page }) => {
  await page.route("**/health", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true, timestamp: "2026-01-26T00:00:00.000Z" })
    });
  });

  await page.goto("/graph?mock=1");

  await expect(page.locator(".react-flow__minimap")).toBeVisible();
  await expect(page.locator(".react-flow__controls")).toBeVisible();
});
