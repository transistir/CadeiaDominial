import { test, expect } from "@playwright/test";

test("home page renders hero content", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /track land records/i })).toBeVisible();
});
