import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import type { Project } from "@/api/contracts";
import { ProjectContext } from "@/features/projects/project-context";
import { ProjectOverviewPage } from "./project-overview";

const projectId = "10000000-0000-4000-8000-000000000001";
const userId = "20000000-0000-4000-8000-000000000001";
const buildId = "30000000-0000-4000-8000-000000000001";

const mocks = vi.hoisted(() => ({
  sources: vi.fn(),
  builds: vi.fn(),
  validation: vi.fn(),
  deployments: vi.fn(),
  deployment: vi.fn(),
  journey: vi.fn(),
}));

vi.mock("@/api/sources", () => ({ sourceApi: { list: mocks.sources } }));
vi.mock("@/api/builds", () => ({
  buildApi: { list: mocks.builds, validation: mocks.validation },
}));
vi.mock("@/api/deployments", () => ({
  deploymentApi: { list: mocks.deployments, get: mocks.deployment },
}));
vi.mock("@/api/projects", () => ({
  projectApi: { journey: mocks.journey },
}));

const project = {
  id: projectId,
  name: "Inventory",
  slug: "inventory",
  description: null,
  is_enabled: true,
  created_by: userId,
  mcp_hostname: "inventory.mcp.example.test",
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
} satisfies Project;

const readyBuild = {
  id: buildId,
  project_id: projectId,
  sequence: 7,
  status: "READY",
  manifest_schema_version: "1.0",
};

const completeJourney = {
  steps: [],
  build_stale: false,
  selected_build_id: buildId,
  access_mode: "external_oauth_oidc",
};

function renderOverview() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ProjectContext.Provider value={project}>
          <ProjectOverviewPage />
        </ProjectContext.Provider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.deployment.mockRejectedValue(new Error("must remain disabled"));
});

test("never collapses delayed authoritative queries into empty setup guidance", () => {
  const pending = new Promise<never>(() => undefined);
  mocks.sources.mockReturnValue(pending);
  mocks.builds.mockReturnValue(pending);
  mocks.deployments.mockReturnValue(pending);
  mocks.journey.mockReturnValue(pending);

  renderOverview();

  expect(
    screen.queryByText("No sources are attached."),
  ).not.toBeInTheDocument();
  expect(screen.queryByText("Not started")).not.toBeInTheDocument();
  expect(screen.queryByText("Not configured")).not.toBeInTheDocument();
  expect(screen.queryByText("Not deployed")).not.toBeInTheDocument();
  expect(
    screen.queryByText("Project setup is incomplete"),
  ).not.toBeInTheDocument();
  expect(screen.getAllByText(/loading/i).length).toBeGreaterThan(3);
});

test("isolates partial failures while preserving successful lifecycle truth", async () => {
  mocks.sources.mockRejectedValue(new Error("source summary unavailable"));
  mocks.builds.mockResolvedValue([readyBuild]);
  mocks.validation.mockRejectedValue(new Error("report unavailable"));
  mocks.deployments.mockResolvedValue([]);
  mocks.journey.mockResolvedValue(completeJourney);

  renderOverview();

  expect(
    await screen.findByText("Source truth could not be loaded"),
  ).toBeVisible();
  expect(screen.getAllByText("Build #7").length).toBeGreaterThan(0);
  expect(
    await screen.findByText("Validation evidence could not be loaded"),
  ).toBeVisible();
  expect(screen.getAllByText("Not deployed").length).toBeGreaterThan(0);
  expect(screen.getByText("external_oauth_oidc")).toBeVisible();
  expect(
    screen.queryByText("Project setup is incomplete"),
  ).not.toBeInTheDocument();
});

test("renders exact immutable validation counts when evidence is available", async () => {
  mocks.sources.mockResolvedValue([]);
  mocks.builds.mockResolvedValue([readyBuild]);
  mocks.validation.mockResolvedValue({
    coverage_percent: 98.5,
    operation_generated_count: 197,
    operation_expected_count: 200,
    blocking_error_count: 0,
    warning_count: 3,
  });
  mocks.deployments.mockResolvedValue([]);
  mocks.journey.mockResolvedValue(completeJourney);

  renderOverview();

  expect(await screen.findAllByText("98.5%")).not.toHaveLength(0);
  expect(screen.getByText("197 of 200")).toBeVisible();
  expect(screen.getByText("Blocking findings")).toBeVisible();
  expect(screen.getByText("Warnings")).toBeVisible();
});
