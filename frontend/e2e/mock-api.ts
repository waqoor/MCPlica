import type { Page, Route } from "@playwright/test";

export const adminUser = {
  id: "00000000-0000-4000-8000-000000000001",
  email: "admin@example.test",
  display_name: "Installation Admin",
  role: "admin",
  is_active: true,
  created_at: "2026-08-26T08:00:00Z",
  updated_at: "2026-08-26T08:00:00Z",
  last_login_at: "2026-08-26T08:00:00Z",
} as const;

export const builderUser = {
  ...adminUser,
  id: "00000000-0000-4000-8000-000000000002",
  email: "builder@example.test",
  display_name: "Project Builder",
  role: "builder",
} as const;

export const readyResponse = {
  ready: true,
  dependencies: {
    postgres: true,
    redis: true,
    milvus: false,
    openrouter: false,
  },
};

export async function json(
  route: Route,
  value: unknown,
  status = 200,
  headers: Record<string, string> = {},
) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(value),
    headers,
  });
}

export async function installCsrfCookie(page: Page) {
  await page.context().addCookies([
    {
      name: "mcplica_csrf",
      value: "e2e-csrf-token",
      url: "http://127.0.0.1:4173",
      sameSite: "Lax",
    },
  ]);
}

export function errorEnvelope(message: string, code = "TEST_ERROR") {
  return { error: { code, message, details: {}, request_id: "e2e-request" } };
}
