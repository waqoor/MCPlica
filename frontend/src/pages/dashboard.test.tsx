import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import { DashboardPage } from "./dashboard";

const mocks = vi.hoisted(() => ({
  listProjects: vi.fn(),
  listBuilds: vi.fn(),
  readiness: vi.fn(),
}));

vi.mock("@/api/projects", () => ({ projectApi: { list: mocks.listProjects } }));
vi.mock("@/api/builds", () => ({ buildApi: { listAll: mocks.listBuilds } }));
vi.mock("@/api/system", () => ({ systemApi: { readiness: mocks.readiness } }));

beforeEach(() => {
  mocks.listProjects.mockResolvedValue([
    {
      id: "project-1",
      name: "Inventory",
      slug: "inventory",
      description: null,
      is_enabled: true,
      created_by: "user-1",
      mcp_hostname: "petstore.mcp.example.test",
      default_base_url: "https://api.example.test",
      created_at: "2026-08-26T10:00:00Z",
      updated_at: "2026-08-26T10:00:00Z",
    },
  ]);
  mocks.listBuilds.mockResolvedValue([
    {
      id: "build-1",
      project_id: "project-1",
      project_name: "Inventory",
      sequence: 3,
      status: "FAILED",
      trigger: "source_change",
      previous_build_id: null,
      compiler_version: null,
      manifest_schema_version: null,
      runtime_compatibility: null,
      analysis_model: null,
      validation_model: null,
      embedding_model: null,
      embedding_dimensions: null,
      prompt_bundle_version: null,
      manifest_sha256: null,
      artifact_sha256: null,
      error_code: "VALIDATION_FAILED",
      error_summary: "Coverage is incomplete",
      created_at: "2026-08-26T10:00:00Z",
      started_at: null,
      completed_at: null,
    },
  ]);
  mocks.readiness.mockResolvedValue({
    status: "degraded",
    checks: [
      { name: "postgres", status: "ready" },
      { name: "openrouter", status: "unavailable" },
    ],
  });
});

test("shows actionable build and dependency failures without billing or chat surfaces", async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );

  expect(await screen.findByText("Review required")).toBeInTheDocument();
  expect(screen.getByText(/1 failed build/)).toBeInTheDocument();
  expect(screen.getByText(/openrouter/i)).toBeInTheDocument();
  expect(screen.queryByText(/billing/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/chat/i)).not.toBeInTheDocument();
});
