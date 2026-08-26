import { expect, test } from "@playwright/test";

const liveEnabled = process.env.E2E_LIVE === "1";
const adminEmail = process.env.E2E_ADMIN_EMAIL;
const adminPassword = process.env.E2E_ADMIN_PASSWORD;

test("authenticates against Compose and exposes the active rollback runtime", async ({
  page,
}) => {
  test.skip(!liveEnabled, "Live Compose acceptance is opt-in");
  test.skip(
    !adminEmail || !adminPassword,
    "Live administrator credentials are required",
  );

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
  await page.getByLabel("Email").fill(adminEmail!);
  await page.getByLabel("Password").fill(adminPassword!);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(
    page.getByRole("heading", { name: "Operational overview" }),
  ).toBeVisible();
  await expect(page).toHaveTitle("MCPlica control plane");

  const navigationToggle = page.getByRole("button", {
    name: "Open navigation",
  });
  if (await navigationToggle.isVisible()) {
    await navigationToggle.click();
  }
  await page.getByRole("link", { name: "Projects" }).click();
  await page
    .getByRole("region", { name: "Project list" })
    .getByRole("link", { name: /MCPlica final acceptance/ })
    .click();

  await expect(
    page.getByRole("heading", { name: "MCPlica final acceptance" }),
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
      .locator("..")
      .getByText("1"),
  ).toBeVisible();

  await page.getByRole("link", { name: "Documentation", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Documentation", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("mcplica-fixture/embedding")).toBeVisible();
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
  expect(cspViolations).toEqual([]);
});
