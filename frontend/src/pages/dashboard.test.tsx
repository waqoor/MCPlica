import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import type { Build, Project } from "@/api/contracts";
import { DashboardPage } from "./dashboard";

const projectId = "10000000-0000-4000-8000-000000000001";
const userId = "20000000-0000-4000-8000-000000000001";
const buildId = "30000000-0000-4000-8000-000000000001";

const mocks = vi.hoisted(() => ({
  listProjects: vi.fn(),
  listBuilds: vi.fn(),
  metrics: vi.fn(),
  readiness: vi.fn(),
}));

vi.mock("@/api/projects", () => ({ projectApi: { list: mocks.listProjects } }));
vi.mock("@/api/builds", () => ({
  buildApi: { listAll: mocks.listBuilds, metrics: mocks.metrics },
}));
vi.mock("@/api/system", () => ({ systemApi: { readiness: mocks.readiness } }));

beforeEach(() => {
  mocks.listProjects.mockResolvedValue([
    {
      id: projectId,
      name: "Inventory",
      slug: "inventory",
      description: null,
      is_enabled: true,
      created_by: userId,
      mcp_hostname: "petstore.mcp.example.test",
      default_base_url: "https://api.example.test",
      active_server_ref: null,
      server_mappings: {},
      active_build_id: null,
      active_deployment_id: null,
      created_at: "2026-08-26T10:00:00Z",
      updated_at: "2026-08-26T10:00:00Z",
      runtime_effect_state: "effective",
      runtime_command_id: null,
      runtime_error_code: null,
    } satisfies Project,
  ]);
  mocks.listBuilds.mockResolvedValue([
    {
      id: buildId,
      project_id: projectId,
      sequence: 3,
      status: "FAILED",
      pipeline_stage: "VALIDATING",
      trigger: "source_change",
      executable_configuration_sha256: null,
      canonical_snapshot_id: null,
      previous_build_id: null,
      compiler_version: "1.0.0",
      manifest_schema_version: "1.0",
      runtime_compatibility: "1.0",
      analysis_model: null,
      validation_model: null,
      embedding_model: null,
      embedding_dimensions: null,
      prompt_bundle_version: null,
      manifest_sha256: null,
      artifact_sha256: null,
      error_code: "VALIDATION_FAILED",
      error_summary: "Coverage is incomplete",
      cancellation_requested_at: null,
      cancellation_requested_by: null,
      cancellation_acknowledged_at: null,
      admission_acquired_at: null,
      admission_enqueued_at: null,
      admission_heartbeat_at: null,
      admission_lease_expires_at: null,
      admission_released_at: null,
      admission_attempt_count: 0,
      created_at: "2026-08-26T10:00:00Z",
      started_at: null,
      completed_at: null,
    } satisfies Build,
  ]);
  mocks.readiness.mockResolvedValue({
    status: "degraded",
    checks: [
      { name: "postgres", status: "ready" },
      { name: "openrouter", status: "unavailable" },
    ],
  });
  mocks.metrics.mockResolvedValue({ total: 90, active: 4, failed: 12 });
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
  expect(screen.getByText(/12 failed build/)).toBeInTheDocument();
  expect(screen.getByText(/12 installation-wide failures/)).toBeInTheDocument();
  expect(screen.getByText(/openrouter/i)).toBeInTheDocument();
  expect(screen.queryByText(/billing/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/chat/i)).not.toBeInTheDocument();
});
