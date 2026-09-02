import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  models: vi.fn(),
  readiness: vi.fn(),
  updateOpenRouter: vi.fn(),
  testOpenRouter: vi.fn(),
}));

vi.mock("@/api/settings", () => ({ settingsApi: mocks }));
vi.mock("@/api/system", () => ({ systemApi: { readiness: mocks.readiness } }));

import { ProviderSettingsPage } from "./provider-settings";

beforeEach(() => {
  mocks.models.mockReset().mockResolvedValue({
    openrouter_configured: true,
    analysis_model: "provider/analysis",
    validation_model: "provider/validation",
    embedding_model: "provider/embedding",
    embedding_dimensions: 1_536,
    include_documentation_in_analysis: false,
    updated_at: null,
  });
  mocks.readiness.mockReset().mockResolvedValue({
    status: "ready",
    checks: [
      { name: "postgres", status: "ready" },
      { name: "openrouter", status: "ready" },
    ],
  });
  mocks.updateOpenRouter.mockReset().mockResolvedValue({
    openrouter_configured: true,
    analysis_model: "provider/analysis",
    validation_model: "provider/validation",
    embedding_model: "provider/embedding",
    embedding_dimensions: 1_536,
    include_documentation_in_analysis: false,
    updated_at: null,
  });
  mocks.testOpenRouter.mockReset().mockResolvedValue({
    ok: true,
    message: "OpenRouter connected; 100 models are visible",
  });
});

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const router = createMemoryRouter(
    [{ path: "/settings/providers", element: <ProviderSettingsPage /> }],
    { initialEntries: ["/settings/providers"] },
  );
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return client;
}

test("exposes a write-only provider key workflow and live readiness rail", async () => {
  renderPage();

  const key = await screen.findByLabelText("New API key");
  expect(key).toHaveAttribute("type", "password");
  expect(key).toHaveAttribute("autocomplete", "new-password");
  expect(screen.getByText("Credential configured")).toBeVisible();
  expect(screen.getByText("Provider reachable")).toBeVisible();
  expect(screen.getByText("Ready for builds")).toBeVisible();
  expect(screen.getAllByText("Ready")).toHaveLength(3);

  await userEvent.type(key, "  sk-or-v1-new-valid-key  ");
  await userEvent.click(screen.getByRole("button", { name: "Rotate API key" }));

  expect(mocks.updateOpenRouter).toHaveBeenCalledWith("sk-or-v1-new-valid-key");
  expect(await screen.findByText(/OpenRouter API key saved/)).toBeVisible();
  expect(key).toHaveValue("");
});

test("validates malformed keys on blur and announces the error", async () => {
  renderPage();

  const key = await screen.findByLabelText("New API key");
  await userEvent.type(key, "short");
  await userEvent.tab();

  expect(
    screen.getByText("The API key must contain 10–500 characters."),
  ).toHaveAttribute("role", "alert");
  expect(screen.getByRole("button", { name: "Rotate API key" })).toBeDisabled();
});

test("tests the saved provider without exposing its credential", async () => {
  renderPage();

  await screen.findByText(
    "A key is configured. Its value cannot be viewed or copied back.",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Test connection" }),
  );

  expect(mocks.testOpenRouter).toHaveBeenCalledTimes(1);
  expect(
    await screen.findByText("OpenRouter connected; 100 models are visible"),
  ).toBeVisible();
});

test("clears stale connection evidence when credential rotation starts", async () => {
  renderPage();

  await userEvent.click(
    await screen.findByRole("button", { name: "Test connection" }),
  );
  expect(
    await screen.findByText("OpenRouter connected; 100 models are visible"),
  ).toBeVisible();

  await userEvent.type(screen.getByLabelText("New API key"), "replacement-key");

  expect(
    screen.queryByText("OpenRouter connected; 100 models are visible"),
  ).not.toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Test connection" }),
  ).toBeDisabled();
});

test("does not claim build readiness until every required model is selected", async () => {
  mocks.models.mockResolvedValueOnce({
    openrouter_configured: true,
    analysis_model: "provider/analysis",
    validation_model: null,
    embedding_model: "provider/embedding",
    embedding_dimensions: 1_536,
    include_documentation_in_analysis: false,
    updated_at: null,
  });
  renderPage();

  expect(
    await screen.findByText(
      "Select analysis, validation, and embedding models in Model settings.",
    ),
  ).toBeVisible();
  expect(screen.getAllByText("Unavailable")).toHaveLength(1);
});
