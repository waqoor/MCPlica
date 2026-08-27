import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  update: vi.fn(),
  readiness: vi.fn(),
  admission: vi.fn(),
}));

vi.mock("@/api/settings", () => ({ settingsApi: mocks }));
vi.mock("@/api/system", () => ({ systemApi: { readiness: mocks.readiness } }));
vi.mock("@/api/builds", () => ({ buildApi: { admission: mocks.admission } }));
vi.mock("@/auth/use-auth", () => ({
  useAuth: () => ({ user: { role: "admin" } }),
}));

import { SettingsPage } from "./settings";

beforeEach(() => {
  mocks.get.mockReset().mockResolvedValue({
    builders_can_deploy: true,
    mcp_base_domain: "mcp.example.test",
    build_concurrency: 4,
    source_retention_days: null,
    build_retention_count: null,
    max_upload_bytes: 10_000_000,
    max_operations_per_project: 1_000,
    max_document_chunks_per_project: 1_000,
    environment: "production",
  });
  mocks.readiness
    .mockReset()
    .mockResolvedValue({ status: "ready", checks: [] });
  mocks.admission.mockReset().mockResolvedValue({
    configured_concurrency: 4,
    effective_concurrency: 4,
    waiting_count: 0,
    active_count: 0,
    queued: [],
  });
});

test("renders nullable retention and enforces exact backend bounds before save", async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const router = createMemoryRouter(
    [{ path: "/settings", element: <SettingsPage /> }],
    { initialEntries: ["/settings"] },
  );
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );

  const retention = await screen.findByLabelText(
    "Source version retention days",
  );
  expect(retention).toHaveValue(null);
  expect(retention).toHaveAttribute("min", "1");
  expect(retention).toHaveAttribute("max", "3650");

  const upload = screen.getByLabelText("Maximum upload bytes");
  await userEvent.clear(upload);
  await userEvent.type(upload, "500000001");
  expect(upload).toHaveAttribute("aria-invalid", "true");
  expect(
    screen.getByRole("button", { name: "Save operational settings" }),
  ).toBeDisabled();
});
