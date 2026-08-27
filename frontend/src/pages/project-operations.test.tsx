import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import type { Build } from "@/api/contracts";
import { ProjectOperationsPage } from "./project-operations";

const projectId = "10000000-0000-4000-8000-000000000001";
const localBuildId = "30000000-0000-4000-8000-000000000001";
const olderBuildId = "30000000-0000-4000-8000-000000000002";
const foreignBuildId = "30000000-0000-4000-8000-000000000099";
const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  get: vi.fn(),
  operations: vi.fn(),
  rebuild: vi.fn(),
  excludeOperation: vi.fn(),
  removeExclusion: vi.fn(),
}));

vi.mock("@/api/builds", () => ({ buildApi: mocks }));
vi.mock("@/features/projects/project-context", () => ({
  useProject: () => ({ id: projectId, active_build_id: localBuildId }),
}));

const localBuild: Build = {
  id: localBuildId,
  project_id: projectId,
  sequence: 1,
  status: "READY",
  pipeline_stage: "READY",
  trigger: "initial",
  executable_configuration_sha256: "a".repeat(64),
  canonical_snapshot_id: "40000000-0000-4000-8000-000000000001",
  previous_build_id: null,
  compiler_version: "1.0.0",
  manifest_schema_version: "mcp-manifest/v1",
  runtime_compatibility: ">=1,<2",
  analysis_model: null,
  validation_model: null,
  embedding_model: null,
  embedding_dimensions: null,
  prompt_bundle_version: null,
  manifest_sha256: null,
  artifact_sha256: null,
  error_code: null,
  error_summary: null,
  cancellation_requested_at: null,
  cancellation_requested_by: null,
  cancellation_acknowledged_at: null,
  admission_acquired_at: null,
  admission_enqueued_at: null,
  admission_heartbeat_at: null,
  admission_lease_expires_at: null,
  admission_released_at: null,
  admission_attempt_count: 0,
  created_at: "2026-08-27T10:00:00Z",
  started_at: "2026-08-27T10:00:01Z",
  completed_at: "2026-08-27T10:01:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.list.mockResolvedValue([localBuild]);
  mocks.operations.mockResolvedValue({
    items: [],
    page: 1,
    page_size: 50,
    policy_change_count: 0,
    total: 0,
  });
});

test("rejects an exact explicit build owned by another project", async () => {
  mocks.get.mockResolvedValue({
    ...localBuild,
    id: foreignBuildId,
    project_id: "10000000-0000-4000-8000-000000000099",
  });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter
        initialEntries={[
          `/projects/${projectId}/tools?build=${foreignBuildId}`,
        ]}
      >
        <Routes>
          <Route
            element={<ProjectOperationsPage />}
            path="/projects/:projectId/tools"
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  expect(await screen.findByText("BUILD_PROJECT_MISMATCH")).toBeInTheDocument();
  expect(screen.getByText(foreignBuildId)).toBeInTheDocument();
  expect(mocks.get).toHaveBeenCalledWith(
    foreignBuildId,
    expect.any(AbortSignal),
  );
  expect(mocks.operations).not.toHaveBeenCalled();
});

test("loads an explicitly selected older build outside bounded history", async () => {
  const olderBuild = { ...localBuild, id: olderBuildId, sequence: 2 };
  mocks.get.mockResolvedValue(olderBuild);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter
        initialEntries={[`/projects/${projectId}/tools?build=${olderBuildId}`]}
      >
        <Routes>
          <Route
            element={<ProjectOperationsPage />}
            path="/projects/:projectId/tools"
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  expect(await screen.findByText("Operations and tools")).toBeInTheDocument();
  expect(screen.getByLabelText("Evidence build")).toHaveValue(olderBuildId);
  expect(mocks.get).toHaveBeenCalledWith(olderBuildId, expect.any(AbortSignal));
  expect(mocks.operations).toHaveBeenCalledWith(
    olderBuildId,
    expect.objectContaining({ page: 1, page_size: 50 }),
    expect.any(AbortSignal),
  );
});

test("loads the active served build exactly when it is outside bounded history", async () => {
  mocks.list.mockResolvedValue([
    { ...localBuild, id: olderBuildId, sequence: 2 },
  ]);
  mocks.get.mockResolvedValue(localBuild);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/projects/${projectId}/tools`]}>
        <Routes>
          <Route
            element={<ProjectOperationsPage />}
            path="/projects/:projectId/tools"
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  expect(await screen.findByText("Operations and tools")).toBeInTheDocument();
  expect(screen.getByLabelText("Evidence build")).toHaveValue(localBuildId);
  expect(mocks.get).toHaveBeenCalledWith(localBuildId, expect.any(AbortSignal));
  expect(mocks.operations).toHaveBeenCalledWith(
    localBuildId,
    expect.any(Object),
    expect.any(AbortSignal),
  );
});
