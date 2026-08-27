import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import { ApiError } from "@/api/client";

const mocks = vi.hoisted(() => ({
  models: vi.fn(),
  modelCatalog: vi.fn(),
  updateModels: vi.fn(),
  updateOpenRouter: vi.fn(),
  testOpenRouter: vi.fn(),
}));

vi.mock("@/api/settings", () => ({ settingsApi: mocks }));

import { ModelSettingsPage } from "./model-settings";

beforeEach(() => {
  mocks.models.mockReset().mockResolvedValue({
    openrouter_configured: true,
    analysis_model: "provider/analysis-current",
    validation_model: "provider/validation-current",
    embedding_model: "provider/embedding-current",
    embedding_dimensions: 1_536,
    include_documentation_in_analysis: false,
    updated_at: "2026-08-27T10:00:00Z",
  });
  mocks.modelCatalog
    .mockReset()
    .mockRejectedValue(
      new ApiError(
        503,
        "The provider catalog is unavailable.",
        "MODEL_CATALOG_UNAVAILABLE",
        {},
        "request-catalog-1",
      ),
    );
});

test("keeps stored model and key recovery controls usable during catalog outage", async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const router = createMemoryRouter(
    [{ path: "/settings/models", element: <ModelSettingsPage /> }],
    { initialEntries: ["/settings/models"] },
  );
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );

  expect(await screen.findByText("Status: configured")).toBeVisible();
  expect(screen.getByLabelText("New API key")).toBeEnabled();
  expect(
    screen.getByRole("button", { name: "Test capabilities" }),
  ).toBeEnabled();
  expect(screen.getByLabelText("Analysis model")).toHaveValue(
    "provider/analysis-current",
  );
  expect(screen.getByText("MODEL_CATALOG_UNAVAILABLE")).toBeVisible();
  expect(screen.getByText("request-catalog-1")).toBeVisible();
  await userEvent.clear(screen.getByLabelText("Analysis model"));
  await userEvent.type(
    screen.getByLabelText("Analysis model"),
    "provider/recovery",
  );
  expect(
    screen.getByRole("button", { name: "Save model policy" }),
  ).toBeEnabled();
});
