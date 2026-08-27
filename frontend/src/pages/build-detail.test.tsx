import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import { BuildDetailPage } from "./build-detail";

const buildId = "30000000-0000-4000-8000-000000000001";
const projectId = "10000000-0000-4000-8000-000000000001";
const snapshotId = "40000000-0000-4000-8000-000000000001";
const sourceVersionId = "50000000-0000-4000-8000-000000000001";
const now = "2026-08-27T10:00:00Z";

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  validation: vi.fn(),
  diff: vi.fn(),
  manifest: vi.fn(),
  aiRuns: vi.fn(),
  cancel: vi.fn(),
  export: vi.fn(),
  downloadManifest: vi.fn(),
}));

vi.mock("@/api/builds", () => ({ buildApi: mocks }));

beforeEach(() => {
  vi.clearAllMocks();
  mocks.get.mockResolvedValue({
    id: buildId,
    project_id: projectId,
    sequence: 7,
    status: "READY",
    pipeline_stage: "READY",
    trigger: "manual_rebuild",
    executable_configuration_sha256: "8".repeat(64),
    canonical_snapshot_id: snapshotId,
    previous_build_id: null,
    compiler_version: "1.0.0",
    manifest_schema_version: "mcp-manifest/v1",
    runtime_compatibility: ">=1,<2",
    analysis_model: "openai/gpt-analysis",
    validation_model: "openai/gpt-validation",
    embedding_model: "openai/embedding",
    embedding_dimensions: 1536,
    prompt_bundle_version: "1.2.0",
    manifest_sha256: "a".repeat(64),
    artifact_sha256: "b".repeat(64),
    error_code: null,
    error_summary: null,
    created_at: now,
    started_at: now,
    completed_at: now,
    cancellation_requested_at: null,
    cancellation_requested_by: null,
    cancellation_acknowledged_at: null,
  });
  mocks.validation.mockResolvedValue({
    id: "60000000-0000-4000-8000-000000000001",
    build_id: buildId,
    overall_status: "pass",
    operation_source_count: 1,
    operation_excluded_count: 0,
    operation_expected_count: 1,
    operation_generated_count: 1,
    coverage_percent: 100,
    blocking_error_count: 0,
    warning_count: 1,
    findings: [
      {
        code: "SEMANTIC_WARNING",
        severity: "warning",
        stage: "analysis",
        operation_key: "GET /pets",
        source_ref: {
          source_version_id: sourceVersionId,
          path: "#/paths/~1pets/get",
        },
        message: "Description is terse",
        details: { confidence: 0.72 },
      },
    ],
    created_at: now,
  });
  mocks.manifest.mockResolvedValue({
    schema_version: "mcp-manifest/v1",
    manifest_id: "c".repeat(64),
    project: {
      id: "10000000-0000-4000-8000-000000000001",
      name: "Pets",
      slug: "pets",
    },
    runtime_compatibility: ">=1,<2",
    servers: [{ id: "primary", url: "https://api.example.com/" }],
    auth_profiles: [],
    tools: [],
    resources: [],
    security: {
      inbound_auth_mode: "static_bearer",
      allowed_upstream_hosts: ["api.example.com"],
      allow_insecure_none_only_in_development: true,
      default_timeout_ms: 30_000,
      default_max_response_bytes: 2_000_000,
    },
    build: {
      build_id: buildId,
      source_version_ids: [sourceVersionId],
      source_digest: "d".repeat(64),
      canonical_sha256: "e".repeat(64),
      created_at: now,
      compiler_version: "1.0.0",
      prompt_bundle_version: "1.2.0",
      analysis_model: "openai/gpt-analysis",
      validation_model: "openai/gpt-validation",
      embedding_model: "openai/embedding",
    },
  });
  mocks.aiRuns.mockResolvedValue([
    {
      id: "70000000-0000-4000-8000-000000000001",
      build_id: buildId,
      run_key: "operation:GET /pets",
      stage: "analysis",
      operation_key: "GET /pets",
      provider: "openrouter",
      model: "openai/gpt-analysis",
      prompt_template_id: "operation-enrichment",
      prompt_template_version: "3",
      input_context_sha256: "f".repeat(64),
      retrieved_chunk_ids: ["chunk-1"],
      response_schema_id: "operation-enrichment/v1",
      response_sha256: "9".repeat(64),
      usage: { input_tokens: 120, output_tokens: 45 },
      cost: { total_usd: 0.0012 },
      latency_ms: 420,
      status: "succeeded",
      error_code: null,
      created_at: now,
    },
  ]);
});

test("renders the immutable manifest, AI identity, and full validation provenance", async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter
        initialEntries={[`/projects/${projectId}/builds/${buildId}`]}
      >
        <Routes>
          <Route
            element={<BuildDetailPage />}
            path="/projects/:projectId/builds/:buildId"
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  expect(await screen.findByText("Immutable MCP manifest")).toBeInTheDocument();
  expect(
    await screen.findByLabelText("Build 7 immutable manifest"),
  ).toHaveTextContent("mcp-manifest/v1");
  expect(screen.getByText("Build-time AI evidence")).toBeInTheDocument();
  expect(screen.getByText("openrouter")).toBeInTheDocument();
  expect(screen.getByText("f".repeat(64))).toBeInTheDocument();
  expect(
    screen.getByText(/Source .* at #\/paths\/~1pets\/get/),
  ).toBeInTheDocument();
  expect(screen.getByText("Expected")).toBeInTheDocument();
  expect(screen.getByText("Warnings")).toBeInTheDocument();
  expect(screen.getByText("Inspect finding details")).toBeInTheDocument();
  expect(
    screen.getByText(/chain-of-thought is never stored/i),
  ).toBeInTheDocument();
});

test("fails closed before loading child evidence for a cross-project build route", async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter
        initialEntries={[`/projects/another-project/builds/${buildId}`]}
      >
        <Routes>
          <Route
            element={<BuildDetailPage />}
            path="/projects/:projectId/builds/:buildId"
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  expect(await screen.findByText("BUILD_PROJECT_MISMATCH")).toBeInTheDocument();
  expect(mocks.validation).not.toHaveBeenCalled();
  expect(mocks.manifest).not.toHaveBeenCalled();
  expect(mocks.aiRuns).not.toHaveBeenCalled();
});

test("confirms cooperative cancellation and shows pending acknowledgement", async () => {
  const requestedAt = "2026-08-27T10:05:00Z";
  const runningBuild = {
    ...(await mocks.get()),
    status: "ANALYZING",
    pipeline_stage: "ANALYZING",
    completed_at: null,
    cancellation_requested_at: null,
    cancellation_requested_by: null,
    cancellation_acknowledged_at: null,
  };
  mocks.get.mockClear();
  mocks.get.mockResolvedValue(runningBuild);
  mocks.cancel.mockResolvedValueOnce({
    ...runningBuild,
    cancellation_requested_at: requestedAt,
    cancellation_requested_by: "90000000-0000-4000-8000-000000000001",
    cancellation_acknowledged_at: null,
  });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const user = userEvent.setup();
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter
        initialEntries={[`/projects/${projectId}/builds/${buildId}`]}
      >
        <Routes>
          <Route
            element={<BuildDetailPage />}
            path="/projects/:projectId/builds/:buildId"
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  await user.click(await screen.findByRole("button", { name: "Cancel" }));
  expect(
    screen.getByText(
      /running parsing, AI, embedding, and packaging work stops/i,
    ),
  ).toBeVisible();
  expect(mocks.cancel).not.toHaveBeenCalled();
  await user.click(
    screen.getByRole("button", { name: "Request cancellation" }),
  );

  expect(await screen.findByText("Cancellation requested")).toBeVisible();
  expect(screen.getByText(/until its worker stops/i)).toBeVisible();
  expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
  expect(mocks.cancel).toHaveBeenCalledTimes(1);
});
