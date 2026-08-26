import { expect, test } from "@playwright/test";
import {
  adminUser,
  errorEnvelope,
  installCsrfCookie,
  json,
  readyResponse,
} from "./mock-api";

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
  let buildCreated = false;
  let accessConfigured = false;
  let accessTokenCreated = false;
  let deployed = false;
  const unknownRequests: string[] = [];
  const mutationCsrfHeaders: Array<string | null> = [];

  const project = {
    id: projectId,
    name: "Inventory API",
    slug: "inventory-api",
    description: "Warehouse inventory operations",
    default_base_url: "https://inventory.example.test/api",
    mcp_hostname: "inventory-api.mcp.example.test",
    is_enabled: true,
    created_by: adminUser.id,
    created_at: now,
    updated_at: now,
  };
  const build = {
    id: buildId,
    project_id: projectId,
    project_name: project.name,
    sequence: 1,
    status: "READY",
    trigger: "initial",
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
  };
  const deployment = {
    id: deploymentId,
    project_id: projectId,
    project_name: project.name,
    build_id: buildId,
    build_sequence: 1,
    status: "RUNNING",
    hostname: project.mcp_hostname,
    endpoint_url: `https://${project.mcp_hostname}/mcp`,
    image_ref: "ghcr.io/example/mcplica-runtime:1",
    image_digest: `sha256:${"c".repeat(64)}`,
    manifest_sha256: build.manifest_sha256,
    health_status: "healthy",
    error_code: null,
    error_summary: null,
    created_at: now,
    started_at: now,
    stopped_at: null,
    failed_at: null,
  };

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
    if (path === "/api/v1/ready") return json(route, readyResponse);
    if (path === "/api/v1/projects" && method === "GET") {
      return json(route, projectCreated ? [project] : []);
    }
    if (path === "/api/v1/projects" && method === "POST") {
      projectCreated = true;
      return json(route, project, 201);
    }
    if (path === `/api/v1/projects/${projectId}` && method === "GET") {
      return json(route, project);
    }
    if (path === `/api/v1/projects/${projectId}` && method === "PATCH") {
      return json(route, { ...project, ...(request.postDataJSON() as object) });
    }
    if (path === `/api/v1/projects/${projectId}/sources` && method === "POST") {
      sourceCreated = true;
      return json(
        route,
        {
          id: sourceId,
          project_id: projectId,
          ...(request.postDataJSON() as object),
          source_url: null,
          created_at: now,
        },
        201,
      );
    }
    if (
      path === `/api/v1/projects/${projectId}/sources/${sourceId}/versions` &&
      method === "POST"
    ) {
      sourceVersionUploads += 1;
      return json(
        route,
        {
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
        },
        201,
      );
    }
    if (path === `/api/v1/projects/${projectId}/builds` && method === "GET") {
      return json(route, buildCreated ? [build] : []);
    }
    if (path === `/api/v1/projects/${projectId}/builds` && method === "POST") {
      buildCreated = true;
      return json(route, build, 201);
    }
    if (path === `/api/v1/builds/${buildId}` && method === "GET") {
      return json(route, build);
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
      return json(route, deployed ? [deployment] : []);
    }
    if (
      path === `/api/v1/projects/${projectId}/deployments` &&
      method === "POST"
    ) {
      deployed = true;
      return json(route, deployment, 201);
    }
    if (path === "/api/v1/builds" && method === "GET") return json(route, []);
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
  await page.getByRole("button", { name: "Save server" }).click();
  await page
    .getByRole("button", { name: "API requires no authentication" })
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
  await page.getByRole("button", { name: "Continue to deploy" }).click();
  await page.getByRole("button", { name: "Deploy runtime" }).click();
  await expect(page.getByText("MCP runtime is healthy")).toBeVisible();

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
