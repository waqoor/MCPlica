import { expect, test } from "@playwright/test";

const liveEnabled = process.env.MCP_LICA_E2E_LIVE === "1";
const adminEmail = process.env.MCP_LICA_E2E_ADMIN_EMAIL;
const adminPassword = process.env.MCP_LICA_E2E_ADMIN_PASSWORD;

test("authenticates against Compose and exposes the active rollback runtime", async ({
  page,
}) => {
  test.skip(!liveEnabled, "Live Compose acceptance is opt-in");
  test.skip(
    !adminEmail || !adminPassword,
    "Live administrator credentials are required",
  );

  await page.goto("/login");
  await page.getByLabel("Email").fill(adminEmail!);
  await page.getByLabel("Password").fill(adminPassword!);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(
    page.getByRole("heading", { name: "Operational overview" }),
  ).toBeVisible();

  await page.getByRole("link", { name: "Projects" }).click();
  await page
    .getByRole("region", { name: "Project list" })
    .getByRole("link", { name: /MCPlica final acceptance/ })
    .click();

  await expect(
    page.getByRole("heading", { name: "MCPlica final acceptance" }),
  ).toBeVisible();
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
});
