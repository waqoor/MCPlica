import { expect, test } from "@playwright/test";

const liveEnabled = process.env.E2E_LIVE === "1";
const adminEmail =
  process.env.E2E_ADMIN_EMAIL ?? process.env.DEFAULT_ADMIN_EMAIL;
const adminPassword =
  process.env.E2E_ADMIN_PASSWORD ?? process.env.DEFAULT_ADMIN_PASSWORD;

test("authenticates against Compose and exposes the active rollback runtime", async ({
  page,
}) => {
  test.skip(!liveEnabled, "Live Compose acceptance is opt-in");
  test.skip(
    !adminEmail || !adminPassword,
    "DEFAULT_ADMIN_EMAIL and DEFAULT_ADMIN_PASSWORD are not configured",
  );
  if (!adminEmail || !adminPassword) {
    return;
  }
  const cspViolations: string[] = [];
  page.on("console", (message) => {
    if (/content-security-policy|unsafe-eval/i.test(message.text())) {
      cspViolations.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    if (/content-security-policy|unsafe-eval/i.test(error.message)) {
      cspViolations.push(error.message);
    }
  });

  await page.goto("/login");
  await page.getByLabel("Email").fill(adminEmail);
  await page.getByLabel("Password").fill(adminPassword);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(
    page.getByRole("heading", { name: "Operational overview" }),
  ).toBeVisible();
  await expect(page).toHaveTitle("MCPlica control plane");

  const openPrimaryNavigation = async () => {
    const navigationToggle = page.getByRole("button", {
      name: "Open navigation",
    });
    if (await navigationToggle.isVisible()) {
      await navigationToggle.click();
    }
  };

  await openPrimaryNavigation();
  await page.getByRole("link", { name: "Projects" }).click();
  await page
    .getByRole("region", { name: "Project list" })
    .getByRole("link", { name: /MCPlica final acceptance/ })
    .first()
    .click();

  await expect(
    page.getByRole("heading", {
      level: 1,
      name: "MCPlica final acceptance",
    }),
  ).toBeVisible();

  await page.getByRole("link", { name: "Sources", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Sources", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Operations", { exact: true }).locator("..").getByText("5"),
  ).toBeVisible();
  await expect(
    page
      .getByText("Indexed chunks", { exact: true })
      .first()
      .locator("..")
      .getByText("1", { exact: true }),
  ).toBeVisible();

  await page.getByRole("link", { name: "Documentation", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Documentation", exact: true }),
  ).toBeVisible();
  await page
    .getByText("Load indexing evidence and sanitized preview", { exact: true })
    .click();
  await expect(
    page.getByText("mcplica-fixture/embedding").first(),
  ).toBeVisible();
  await expect(page.getByText("Pending index", { exact: true })).toHaveCount(0);

  await page.getByRole("link", { name: "Deployment", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Deployment and MCP access" }),
  ).toBeVisible();
  await expect(
    page.getByText("Running", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByText("Healthy", { exact: true }).first(),
  ).toBeVisible();

  await openPrimaryNavigation();
  await page
    .getByRole("navigation", { name: "Primary" })
    .getByRole("link", { name: "Settings" })
    .click();
  await expect(
    page.getByRole("heading", { level: 1, name: "Settings" }),
  ).toBeVisible();
  await page
    .getByRole("navigation", { name: "Settings sections" })
    .getByRole("link", { name: "Providers" })
    .click();
  await expect(
    page.getByRole("heading", { level: 1, name: "Providers" }),
  ).toBeVisible();
  await expect(page.getByText("https://openrouter.ai/api/v1")).toBeVisible();
  const providerResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/api/v1/settings/openrouter/test"),
  );
  await page.getByRole("button", { name: "Test connection" }).click();
  const providerResponse = await providerResponsePromise;
  expect(providerResponse.ok()).toBe(true);
  const providerResult = (await providerResponse.json()) as { ok?: unknown };
  expect(providerResult.ok).toBe(true);
  await expect(
    page.getByText(/OpenRouter connected; \d+ models are visible/),
  ).toBeVisible({
    timeout: 30_000,
  });
  expect(cspViolations).toEqual([]);
});
