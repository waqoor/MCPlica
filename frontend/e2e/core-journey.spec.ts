import { expect, test } from "@playwright/test";
import {
  adminUser,
  errorEnvelope,
  installCsrfCookie,
  json,
  readyResponse,
} from "./mock-api";
import type {
  Build,
  BuildMetrics,
  BuildPage,
  Deployment,
  DeploymentPage,
  OperationPage,
  Project,
  ProjectJourney,
  SourceConfigurationDiscovery,
  SystemSettings,
} from "../src/api/contracts";
import type { components } from "../src/api/generated/schema";

test("completes the durable source-to-runtime journey through typed contracts", async ({
  page,
}, testInfo) => {
  test.skip(
    testInfo.project.name === "mobile-chromium",
    "The mobile-specific navigation test covers the compact shell.",
  );

  const projectId = "10000000-0000-4000-8000-000000000001";
  const sourceId = "20000000-0000-4000-8000-000000000001";
  const versionId = "30000000-0000-4000-8000-000000000001";
  const buildId = "40000000-0000-4000-8000-000000000001";
  const tokenId = "50000000-0000-4000-8000-000000000001";
  const deploymentId = "60000000-0000-4000-8000-000000000001";
  const now = "2026-08-26T08:00:00Z";
  let authenticated = false;
  let projectCreated = false;
  let sourceCreated = false;
  let sourceVersionUploads = 0;
  let routingConfigured = false;
  let buildCreated = false;
  let accessConfigured = false;
  let accessTokenCreated = false;
  let deployed = false;
  const unknownRequests: string[] = [];
  const mutationCsrfHeaders: Array<string | null> = [];

  const project = (): Project => ({
    id: projectId,
    name: "Inventory API",
    slug: "inventory-api",
    description: "Warehouse inventory operations",
    default_base_url: routingConfigured
      ? "https://inventory.example.test/api"
      : null,
    active_server_ref: null,
    server_mappings: {},
    mcp_hostname: "inventory-api.mcp.example.test",
    is_enabled: true,
    active_build_id: buildCreated ? buildId : null,
    active_deployment_id: deployed ? deploymentId : null,
    created_by: adminUser.id,
    created_at: now,
    updated_at: now,
    runtime_effect_state: "effective",
    runtime_command_id: null,
    runtime_error_code: null,
  });
  const build = {
    id: buildId,
    project_id: projectId,
    sequence: 1,
    status: "READY",
    pipeline_stage: "READY",
    trigger: "initial",
    executable_configuration_sha256: "7".repeat(64),
    canonical_snapshot_id: "88888888-8888-4888-8888-888888888888",
    previous_build_id: null,
    compiler_version: "1.0.0",
    manifest_schema_version: "1.0",
    runtime_compatibility: "1.0",
    analysis_model: null,
    validation_model: null,
    embedding_model: null,
    embedding_dimensions: null,
    prompt_bundle_version: null,
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
    admission_acquired_at: now,
    admission_enqueued_at: now,
    admission_heartbeat_at: now,
    admission_lease_expires_at: null,
    admission_released_at: now,
    admission_attempt_count: 1,
  } satisfies Build;
  const operation = {
    key: "HEAD /inventory",
    source_operation_id: "inspectInventoryHeaders",
    method: "HEAD",
    path_template: "/inventory",
    tool_name: "inspect_inventory_headers",
    title: "Inspect inventory response headers",
    source_summary: "Inspect inventory headers",
    source_description: "Returns inventory response headers only.",
    enriched_description:
      "Inspect cache and rate-limit headers without a response body.",
    input_schema: { type: "object", additionalProperties: false },
    auth_mapping: [],
    provenance: [
      {
        source_version_id: versionId,
        path: "#/paths/~1inventory/head",
        kind: "source",
      },
    ],
    semantic_warnings: ["Confirm upstream HEAD parity with GET."],
    confidence: 0.88,
    excluded_in_build: false,
    build_exclusion_id: null,
    build_exclusion_reason: null,
    current_exclusion_id: null,
    current_exclusion_reason: null,
  } satisfies OperationPage["items"][number];
  const deployment = {
    id: deploymentId,
    project_id: projectId,
    build_id: buildId,
    intent: "normal",
    status: "running",
    hostname: "inventory-api.mcp.example.test",
    endpoint_url: "https://inventory-api.mcp.example.test/mcp",
    image_ref: "ghcr.io/example/mcplica-runtime:1",
    image_digest: `sha256:${"c".repeat(64)}`,
    manifest_sha256: build.manifest_sha256,
    container_id: "container-1",
    container_name: "mcplica-inventory-api",
    network_name: "mcplica-runtime",
    runtime_version: "1.0.0",
    auth_overlay_sha256: "e".repeat(64),
    health_status: "healthy",
    error_code: null,
    error_summary: null,
    created_at: now,
    started_at: now,
    activated_at: now,
    activation_phase: "running",
    activation_verified_at: now,
    activation_proof_sha256: "f".repeat(64),
    stopped_at: null,
    failed_at: null,
    rollback_eligible: true,
  } satisfies Deployment;
  const source = {
    id: sourceId,
    project_id: projectId,
    kind: "openapi",
    name: "Primary API specification",
    origin_type: "upload",
    source_url: null,
    is_primary: true,
    current_version_id: versionId,
    current_version_selected_at: now,
    last_observed_at: now,
    last_observed_etag: null,
    last_observed_last_modified: null,
    created_at: now,
  } satisfies components["schemas"]["SourceRead"];
  const sourceVersion = {
    id: versionId,
    source_id: sourceId,
    content_sha256: "d".repeat(64),
    media_type: "application/json",
    byte_size: 74,
    detected_format: "openapi-3.1-json",
    source_etag: null,
    source_last_modified: null,
    created_by: adminUser.id,
    created_at: now,
    deduplicated: false,
  } satisfies components["schemas"]["SourceVersionRead"];
  const sourceConfiguration = (): SourceConfigurationDiscovery => ({
    source_version_ids: sourceCreated ? [versionId] : [],
    configuration_sha256: "9".repeat(64),
    servers: [],
    operations: [],
    security_schemes: [],
    security_requirements: [],
    routing_complete: sourceCreated && routingConfigured,
  });
  const journey = (requestedBuildId: string | null): ProjectJourney => {
    const routingComplete = sourceCreated && routingConfigured;
    const accessReady = accessConfigured && accessTokenCreated;
    const completed: Record<number, boolean> = {
      1: true,
      2: sourceCreated,
      3: sourceCreated,
      4: routingComplete,
      5: routingComplete,
      6: buildCreated,
      7: buildCreated,
      8: buildCreated,
      9: accessReady,
      10: deployed,
    };
    const resumeStep =
      Array.from({ length: 9 }, (_, index) => index + 2).find(
        (number) => !completed[number],
      ) ?? 10;
    const preflightReady = buildCreated && accessReady;
    return {
      project_id: projectId,
      requested_build_id: requestedBuildId,
      selected_build_id: buildCreated ? buildId : null,
      active_build_id: buildCreated ? buildId : null,
      active_deployment_id: deployed ? deploymentId : null,
      resume_step: resumeStep,
      steps: Array.from({ length: 10 }, (_, index) => {
        const number = index + 1;
        return {
          number,
          state: completed[number]
            ? "complete"
            : number === resumeStep
              ? "current"
              : "locked",
          authorized: true,
          reason_code: completed[number] ? null : "STEP_INCOMPLETE",
          message: completed[number] ? null : "Complete this durable step.",
          remediation: completed[number] ? null : "Continue the guided setup.",
        };
      }),
      sources: sourceCreated
        ? [
            {
              id: sourceId,
              version_id: versionId,
              kind: "openapi",
              name: source.name,
              is_primary: true,
            },
          ]
        : [],
      source_version_ids: sourceCreated ? [versionId] : [],
      routing_complete: routingComplete,
      credential_mapping_required: false,
      credential_mapping_complete: routingComplete,
      bound_security_schemes: [],
      access_mode: accessConfigured ? "static_bearer" : null,
      access_configured: accessReady,
      access_runtime_effect_state: "effective",
      access_remediation: accessReady
        ? null
        : "Create an active verifier token.",
      build_status: buildCreated ? "READY" : null,
      build_stale: false,
      validation_status: buildCreated ? "pass" : null,
      validation_complete: buildCreated,
      active_deployment_status: deployed ? "running" : null,
      deployment_transition_in_progress: false,
      preflight_ready: preflightReady,
      deployable: preflightReady && !deployed,
      deployability_reason_code: preflightReady ? null : "SETUP_INCOMPLETE",
      deployability_remediation: preflightReady
        ? null
        : "Complete build validation and access configuration.",
      can_manage_credentials: true,
      can_manage_mcp_access: true,
      can_deploy: true,
    };
  };
  const systemSettings = {
    builders_can_deploy: false,
    mcp_base_domain: "mcp.example.test",
    build_concurrency: 2,
    source_retention_days: 90,
    build_retention_count: 20,
    max_upload_bytes: 100_000_000,
    max_operations_per_project: 5_000,
    max_document_chunks_per_project: 100_000,
    environment: "test",
  } satisfies SystemSettings;

  await installCsrfCookie(page);
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    if (
      !["GET", "HEAD", "OPTIONS"].includes(method) &&
      path !== "/api/v1/auth/login"
    ) {
      mutationCsrfHeaders.push(await request.headerValue("x-csrf-token"));
    }

    if (path === "/api/v1/auth/me" && method === "GET") {
      return authenticated
        ? json(route, adminUser)
        : json(
            route,
            errorEnvelope("Authentication is required", "AUTH_REQUIRED"),
            401,
          );
    }
    if (path === "/api/v1/auth/login" && method === "POST") {
      authenticated = true;
      return json(route, { user: adminUser, access_expires_at: now });
    }
    if (path === "/api/v1/auth/refresh" && method === "POST") {
      return json(route, errorEnvelope("Refresh session is unavailable"), 401);
    }
    if (path === "/api/v1/ready") return json(route, readyResponse);
    if (path === "/api/v1/settings" && method === "GET") {
      return json(route, systemSettings);
    }
    if (path === "/api/v1/projects" && method === "GET") {
      return json(route, projectCreated ? [project()] : []);
    }
    if (path === "/api/v1/projects" && method === "POST") {
      projectCreated = true;
      return json(route, project(), 201);
    }
    if (path === `/api/v1/projects/${projectId}` && method === "GET") {
      return json(route, project());
    }
    if (path === `/api/v1/projects/${projectId}` && method === "PATCH") {
      routingConfigured = true;
      return json(route, {
        ...project(),
        ...(request.postDataJSON() as object),
      });
    }
    if (path === `/api/v1/projects/${projectId}/journey` && method === "GET") {
      return json(route, journey(url.searchParams.get("build_id")));
    }
    if (
      path === `/api/v1/projects/${projectId}/source-configuration` &&
      method === "GET"
    ) {
      return json(route, sourceConfiguration());
    }
    if (
      path === `/api/v1/projects/${projectId}/sources/upload` &&
      method === "POST"
    ) {
      sourceCreated = true;
      sourceVersionUploads += 1;
      return json(route, { source, version: sourceVersion }, 201);
    }
    if (path === `/api/v1/projects/${projectId}/builds` && method === "GET") {
      return json(route, {
        items: buildCreated ? [build] : [],
        total: buildCreated ? 1 : 0,
        page: Number(url.searchParams.get("page") ?? 1),
        page_size: Number(url.searchParams.get("page_size") ?? 50),
        has_active: false,
      } satisfies BuildPage);
    }
    if (path === `/api/v1/projects/${projectId}/builds` && method === "POST") {
      buildCreated = true;
      return json(route, build, 201);
    }
    if (path === `/api/v1/builds/${buildId}` && method === "GET") {
      return json(route, build);
    }
    if (path === `/api/v1/builds/${buildId}/operations` && method === "GET") {
      return json(route, {
        items: [operation],
        total: 1,
        page: Number(url.searchParams.get("page") ?? 1),
        page_size: Number(url.searchParams.get("page_size") ?? 50),
        policy_change_count: 0,
      } satisfies OperationPage);
    }
    if (
      path === `/api/v1/projects/${projectId}/operation-exclusions` &&
      method === "GET"
    ) {
      return json(route, []);
    }
    if (path === `/api/v1/builds/${buildId}/validation` && method === "GET") {
      return json(route, {
        id: "70000000-0000-4000-8000-000000000001",
        build_id: buildId,
        overall_status: "pass",
        operation_source_count: 2,
        operation_excluded_count: 0,
        operation_expected_count: 2,
        operation_generated_count: 2,
        coverage_percent: 100,
        blocking_error_count: 0,
        warning_count: 0,
        findings: [],
        created_at: now,
      });
    }
    if (
      path === `/api/v1/projects/${projectId}/mcp-access` &&
      method === "GET"
    ) {
      return json(route, {
        auth_config: accessConfigured
          ? {
              project_id: projectId,
              mode: "static_bearer",
              issuer_url: null,
              audiences: [],
              required_scopes: [],
              metadata: {},
              updated_by: adminUser.id,
              updated_at: now,
              runtime_effect_state: "effective",
              runtime_command_id: null,
              runtime_error_code: null,
            }
          : null,
        tokens: accessTokenCreated
          ? [
              {
                id: tokenId,
                project_id: projectId,
                name: "Primary MCP client",
                token_prefix: "mcp_live_",
                created_by: adminUser.id,
                created_at: now,
                expires_at: null,
                last_used_at: null,
                revoked_at: null,
                runtime_effect_state: "effective",
                runtime_command_id: null,
                runtime_error_code: null,
              },
            ]
          : [],
      });
    }
    if (
      path === `/api/v1/projects/${projectId}/mcp-access/auth-mode` &&
      method === "PUT"
    ) {
      accessConfigured = true;
      return json(route, {
        project_id: projectId,
        mode: "static_bearer",
        issuer_url: null,
        audiences: [],
        required_scopes: [],
        metadata: {},
        updated_by: adminUser.id,
        updated_at: now,
        runtime_effect_state: "effective",
        runtime_command_id: null,
        runtime_error_code: null,
      });
    }
    if (
      path === `/api/v1/projects/${projectId}/mcp-access/tokens` &&
      method === "POST"
    ) {
      accessTokenCreated = true;
      return json(
        route,
        {
          token: {
            id: tokenId,
            project_id: projectId,
            name: "Primary MCP client",
            token_prefix: "mcp_live_",
            created_by: adminUser.id,
            created_at: now,
            expires_at: null,
            last_used_at: null,
            revoked_at: null,
            runtime_effect_state: "effective",
            runtime_command_id: null,
            runtime_error_code: null,
          },
          plaintext: "mcp_live_one_time_secret",
        },
        201,
      );
    }
    if (
      path === `/api/v1/projects/${projectId}/deployments` &&
      method === "GET"
    ) {
      return json(route, {
        items: deployed ? [deployment] : [],
        total: deployed ? 1 : 0,
        page: Number(url.searchParams.get("page") ?? 1),
        page_size: Number(url.searchParams.get("page_size") ?? 50),
        has_active: false,
      } satisfies DeploymentPage);
    }
    if (
      path === `/api/v1/projects/${projectId}/deployments` &&
      method === "POST"
    ) {
      deployed = true;
      return json(route, deployment, 201);
    }
    if (path === `/api/v1/deployments/${deploymentId}` && method === "GET") {
      return json(route, deployment);
    }
    if (path === "/api/v1/builds/metrics" && method === "GET") {
      return json(route, {
        total: buildCreated ? 1 : 0,
        active: 0,
        failed: 0,
      } satisfies BuildMetrics);
    }
    if (path === "/api/v1/builds" && method === "GET") {
      return json(route, {
        items: buildCreated ? [build] : [],
        total: buildCreated ? 1 : 0,
        page: Number(url.searchParams.get("page") ?? 1),
        page_size: Number(url.searchParams.get("page_size") ?? 50),
        has_active: false,
      } satisfies BuildPage);
    }
    unknownRequests.push(`${method} ${path}${url.search}`);
    return json(route, errorEnvelope("Unexpected E2E request"), 404);
  });

  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@example.test");
  await page.getByLabel("Password").fill("correct horse battery staple");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(
    page.getByRole("heading", { name: "Operational overview" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "New project" }).click();

  await page.getByLabel("Project name").fill("Inventory API");
  await page.getByLabel("Description").fill("Warehouse inventory operations");
  await page.getByRole("button", { name: "Create and continue" }).click();
  await expect(page.getByText("Step 2 of 10")).toBeVisible();

  await page.getByLabel("Source file").setInputFiles({
    name: "openapi.json",
    mimeType: "application/json",
    buffer: Buffer.from(
      JSON.stringify({
        openapi: "3.1.0",
        info: { title: "Inventory", version: "1" },
        paths: {},
      }),
    ),
  });
  await page.getByRole("button", { name: "Add source and continue" }).click();
  await page.getByRole("button", { name: "Skip documentation" }).click();

  await page.getByLabel("Base URL").fill("https://inventory.example.test/api");
  await page.getByRole("button", { name: "Save validated routing" }).click();
  await page
    .getByRole("button", { name: "Continue without an upstream credential" })
    .click();
  await page.getByRole("button", { name: "Start build" }).click();
  await expect(page.getByText("Step 7 of 10")).toBeVisible();
  await page.getByRole("button", { name: "Review validation" }).click();
  await expect(page.getByText("Validation passed")).toBeVisible();
  await page.getByRole("button", { name: "Configure MCP access" }).click();

  await page
    .getByRole("button", { name: "Use static bearer authentication" })
    .click();
  await page.getByRole("button", { name: "Create access token" }).click();
  await expect(page.getByText("mcp_live_one_time_secret")).toBeVisible();
  await page
    .getByRole("checkbox", {
      name: "I have stored this token securely and understand it cannot be shown again.",
    })
    .check();
  await page.getByRole("button", { name: "Finish and hide token" }).click();
  await page.getByRole("button", { name: "Continue to deploy" }).click();
  await page.getByRole("button", { name: "Deploy runtime" }).click();
  await expect(page.getByText("MCP runtime is healthy")).toBeVisible();

  await page.goto(`/projects/${projectId}/tools`);
  await expect(page).toHaveURL(new RegExp(`[?&]build=${buildId}`));
  await expect(
    page.getByText("Inspect inventory response headers"),
  ).toBeVisible();
  await expect(
    page.getByText("Confirm upstream HEAD parity with GET."),
  ).toBeVisible();
  await page.getByLabel("Method").selectOption("HEAD");
  await expect(page.getByText("/inventory", { exact: true })).toBeVisible();

  expect(projectCreated).toBe(true);
  expect(sourceCreated).toBe(true);
  expect(sourceVersionUploads).toBe(1);
  expect(buildCreated).toBe(true);
  expect(accessConfigured).toBe(true);
  expect(deployed).toBe(true);
  expect(mutationCsrfHeaders).not.toHaveLength(0);
  expect(new Set(mutationCsrfHeaders)).toEqual(new Set(["e2e-csrf-token"]));
  expect(unknownRequests).toEqual([]);
});
