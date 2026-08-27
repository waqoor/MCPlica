import { expect, test } from "@playwright/test";
import {
  builderUser,
  errorEnvelope,
  installCsrfCookie,
  json,
  readyResponse,
} from "./mock-api";
import type { BuildMetrics, BuildPage } from "../src/api/contracts";

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
    if (path === "/api/v1/builds/metrics") {
      return json(route, {
        total: 0,
        active: 0,
        failed: 0,
      } satisfies BuildMetrics);
    }
    if (path === "/api/v1/builds") {
      return json(route, {
        items: [],
        total: 0,
        page: 1,
        page_size: 50,
        has_active: false,
      } satisfies BuildPage);
    }
    if (path === "/api/v1/ready") return json(route, readyResponse);
    return json(route, errorEnvelope("Unexpected E2E request"), 404);
  });
}

test("preserves the protected destination and fails closed for builder-only access", async ({
  page,
  baseURL,
}) => {
  if (!baseURL) throw new Error("Playwright baseURL is required");
  await installCsrfCookie(page);
  await installShellApi(page, false);
  await page.goto("/settings/users");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText("Public registration is disabled")).toBeVisible();
  await page.getByLabel("Email").fill("builder@example.test");
  await page.getByLabel("Password").fill("builder-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(new URL("/", baseURL).href);
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

test("loads the supplied transparent PNG for the active shell brand variant", async ({
  page,
}, testInfo) => {
  await installShellApi(page);
  const brandRequests = new Set<string>();
  page.on("request", (request) => {
    const pathname = new URL(request.url()).pathname;
    if (/\/assets\/logo(?:_draw_only)?-[^/]+\.(?:png|webp)$/.test(pathname)) {
      brandRequests.add(pathname);
    }
  });

  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Operational overview" }),
  ).toBeVisible();
  await page.waitForLoadState("networkidle");

  const shellLogo = page.locator(
    "header img[src*='/assets/logo'], aside img[src*='/assets/logo']",
  );
  await expect(shellLogo).toHaveCount(1);
  const activeSource = await shellLogo.getAttribute("src");
  expect(activeSource).not.toBeNull();
  expect(
    [...brandRequests].every((pathname) => pathname.endsWith(".png")),
  ).toBe(true);
  const renderedAsset = await shellLogo.evaluate((image) => {
    const wrapper = image.parentElement;
    if (!wrapper) throw new Error("Brand logo wrapper is missing");
    const wrapperStyle = getComputedStyle(wrapper);
    return {
      naturalHeight: (image as HTMLImageElement).naturalHeight,
      naturalWidth: (image as HTMLImageElement).naturalWidth,
      wrapperBackground: wrapperStyle.backgroundColor,
      wrapperBorderStyle: wrapperStyle.borderStyle,
    };
  });
  expect(renderedAsset.wrapperBackground).toBe("rgba(0, 0, 0, 0)");
  expect(renderedAsset.wrapperBorderStyle).toBe("none");
  if (testInfo.project.name === "mobile-chromium") {
    expect(activeSource).toContain("logo_draw_only-");
    expect(renderedAsset).toMatchObject({
      naturalHeight: 887,
      naturalWidth: 1774,
    });
    expect(
      [...brandRequests].every((pathname) =>
        pathname.includes("logo_draw_only-"),
      ),
    ).toBe(true);
  } else {
    expect(activeSource).toMatch(/\/assets\/logo-[^/]+\.png$/);
    expect(renderedAsset).toMatchObject({
      naturalHeight: 941,
      naturalWidth: 1672,
    });
  }
});

test("keeps primary navigation operable on a compact viewport", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "mobile-chromium", "Compact shell only");
  await installShellApi(page);
  await page.goto("/");
  const opener = page.getByRole("button", { name: "Open navigation" });
  await opener.click();
  await expect(
    page.getByRole("dialog", { name: "Navigation" }),
  ).toHaveAttribute("aria-modal", "true");
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
  await expect
    .poll(() => page.evaluate(() => document.body.style.overflow))
    .toBe("hidden");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "Navigation" })).toHaveCount(0);
  await expect(opener).toBeFocused();
  await expect
    .poll(() => page.evaluate(() => document.body.style.overflow))
    .toBe("");

  await opener.click();
  await page.getByRole("link", { name: "Projects" }).click();
  await expect(page).toHaveURL(/\/projects$/);
  await expect(page.getByRole("navigation", { name: "Primary" })).toHaveCount(
    0,
  );
});
