import { expect, test } from "@playwright/test";
import {
  builderUser,
  errorEnvelope,
  installCsrfCookie,
  json,
  readyResponse,
} from "./mock-api";

async function installShellApi(
  page: Parameters<typeof installCsrfCookie>[0],
  authenticated = true,
) {
  let signedIn = authenticated;
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/v1/auth/me") {
      return signedIn
        ? json(route, builderUser)
        : json(
            route,
            errorEnvelope("Authentication is required", "AUTH_REQUIRED"),
            401,
          );
    }
    if (path === "/api/v1/auth/login") {
      signedIn = true;
      return json(route, {
        user: builderUser,
        access_expires_at: "2026-08-26T09:00:00Z",
      });
    }
    if (path === "/api/v1/projects") return json(route, []);
    if (path === "/api/v1/builds") return json(route, []);
    if (path === "/api/v1/ready") return json(route, readyResponse);
    return json(route, errorEnvelope("Unexpected E2E request"), 404);
  });
}

test("preserves the protected destination and fails closed for builder-only access", async ({
  page,
}) => {
  await installCsrfCookie(page);
  await installShellApi(page, false);
  await page.goto("/settings/users");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText("Public registration is disabled")).toBeVisible();
  await page.getByLabel("Email").fill("builder@example.test");
  await page.getByLabel("Password").fill("builder-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL("http://127.0.0.1:4173/");
  await expect(
    page.getByRole("heading", { name: "Operational overview" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Users" })).toHaveCount(0);
});

test("supports keyboard bypass navigation and excludes prohibited product areas", async ({
  page,
  browserName,
}) => {
  await installShellApi(page);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Operational overview" }),
  ).toBeVisible();
  const skipLink = page.getByRole("link", { name: "Skip to main content" });
  if (browserName === "webkit") {
    // Safari delegates whether Tab focuses links to the host full-keyboard-access
    // preference. Focus the same target explicitly, then prove keyboard activation.
    await skipLink.focus();
  } else {
    await page.keyboard.press("Tab");
  }
  await expect(skipLink).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
  await expect(
    page
      .locator("nav a")
      .filter({ hasText: /Chat|Agents|Billing|Entitlements/i }),
  ).toHaveCount(0);
});

test("keeps primary navigation operable on a compact viewport", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "mobile-chromium", "Compact shell only");
  await installShellApi(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
  await page.getByRole("link", { name: "Projects" }).click();
  await expect(page).toHaveURL(/\/projects$/);
  await expect(page.getByRole("navigation", { name: "Primary" })).toHaveCount(
    0,
  );
});
