import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import type { Build } from "@/api/contracts";
import { ProjectDeploymentPage } from "./project-deployment";

const projectId = "10000000-0000-4000-8000-000000000001";
const firstBuildId = "30000000-0000-4000-8000-000000000001";
const secondBuildId = "30000000-0000-4000-8000-000000000002";

const mocks = vi.hoisted(() => ({
  listBuilds: vi.fn(),
  listDeployments: vi.fn(),
  accessStatus: vi.fn(),
}));

vi.mock("@/api/builds", () => ({
  buildApi: { list: mocks.listBuilds },
}));
vi.mock("@/api/deployments", () => ({
  deploymentApi: {
    accessStatus: mocks.accessStatus,
    listPage: mocks.listDeployments,
  },
}));
vi.mock("@/auth/capabilities", () => ({
  useCapabilities: () => ({
    canDeploy: true,
    canManageMcpAccess: false,
  }),
}));
vi.mock("@/features/projects/project-context", () => ({
  useProject: () => ({
    id: projectId,
    active_deployment_id: null,
  }),
}));

const readyBuild = (id: string, sequence: number): Build => ({
  id,
  project_id: projectId,
  sequence,
  status: "READY",
  pipeline_stage: "READY",
  trigger: "initial",
  executable_configuration_sha256: "a".repeat(64),
  canonical_snapshot_id: `40000000-0000-4000-8000-00000000000${sequence}`,
  previous_build_id: null,
  compiler_version: "1.0.0",
  manifest_schema_version: "mcp-manifest/v1",
  runtime_compatibility: ">=1,<2",
  analysis_model: null,
  validation_model: null,
  embedding_model: null,
  embedding_dimensions: null,
  prompt_bundle_version: null,
  manifest_sha256: "b".repeat(64),
  artifact_sha256: "c".repeat(64),
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
});

function HistoryHarness() {
  const navigate = useNavigate();
  return (
    <>
      <button onClick={() => void navigate(-1)} type="button">
        Browser back
      </button>
      <button onClick={() => void navigate(1)} type="button">
        Browser forward
      </button>
      <ProjectDeploymentPage />
    </>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.listBuilds.mockResolvedValue([
    readyBuild(firstBuildId, 1),
    readyBuild(secondBuildId, 2),
  ]);
  mocks.listDeployments.mockResolvedValue({
    items: [],
    page: 1,
    page_size: 25,
    total: 0,
    has_active: false,
  });
  mocks.accessStatus.mockResolvedValue({
    project_id: projectId,
    mode: "static_bearer",
    issuer_url: null,
    jwks_url: null,
    audiences: [],
    required_scopes: [],
    allowed_algorithms: [],
    updated_at: "2026-08-27T10:00:00Z",
    configured: true,
    runtime_effect_state: "effective",
    runtime_command_id: null,
    runtime_error_code: null,
  });
});

test("stores READY-build selection in the URL and restores it with history", async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const user = userEvent.setup();
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter
        initialEntries={[
          `/projects/${projectId}/deployment?build=${firstBuildId}`,
        ]}
      >
        <Routes>
          <Route
            element={<HistoryHarness />}
            path="/projects/:projectId/deployment"
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  const selector = await screen.findByLabelText("Build");
  expect(selector).toHaveValue(firstBuildId);

  await user.selectOptions(selector, secondBuildId);
  expect(selector).toHaveValue(secondBuildId);

  await user.click(screen.getByRole("button", { name: "Browser back" }));
  expect(selector).toHaveValue(firstBuildId);

  await user.click(screen.getByRole("button", { name: "Browser forward" }));
  expect(selector).toHaveValue(secondBuildId);
});
