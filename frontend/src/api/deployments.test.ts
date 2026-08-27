import { afterEach, expect, test, vi } from "vitest";
import { deploymentApi } from "./deployments";

afterEach(() => vi.restoreAllMocks());

const projectId = "10000000-0000-4000-8000-000000000001";
const userId = "20000000-0000-4000-8000-000000000001";
const tokenId = "30000000-0000-4000-8000-000000000001";
const buildId = "40000000-0000-4000-8000-000000000001";
const deploymentId = "50000000-0000-4000-8000-000000000001";
const now = "2026-08-26T10:00:00Z";

test("preserves deployment history totals and installation-wide active state", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        items: [],
        total: 231,
        page: 5,
        page_size: 25,
        has_active: true,
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );

  await expect(
    deploymentApi.listPage(projectId, { page: 5, page_size: 25 }),
  ).resolves.toMatchObject({ total: 231, page: 5, has_active: true });
  expect(String(fetchMock.mock.calls[0][0])).toBe(
    `/api/v1/projects/${projectId}/deployments?page=5&page_size=25`,
  );
});

test("normalizes MCP access without weakening static-token readiness", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        auth_config: {
          project_id: projectId,
          mode: "static_bearer",
          issuer_url: null,
          audiences: [],
          required_scopes: [],
          metadata: {
            jwks_url: "https://issuer.example/keys",
            allowed_algorithms: ["RS256"],
          },
          updated_by: userId,
          updated_at: now,
          runtime_effect_state: "effective",
          runtime_command_id: null,
          runtime_error_code: null,
        },
        tokens: [],
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );

  await expect(deploymentApi.access(projectId)).resolves.toMatchObject({
    project_id: projectId,
    mode: "static_bearer",
    configured: false,
    jwks_url: "https://issuer.example/keys",
    allowed_algorithms: ["RS256"],
    tokens: [],
  });
});

test("sends the selected token rotation overlap and maps its one-time value", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        token: {
          id: tokenId,
          project_id: projectId,
          name: "Desktop",
          token_prefix: "mcp_new",
          created_by: userId,
          created_at: now,
          expires_at: null,
          last_used_at: null,
          revoked_at: null,
          runtime_effect_state: "pending",
          runtime_command_id: deploymentId,
          runtime_error_code: null,
        },
        plaintext: "mcp_rotated_once",
      }),
      { status: 201, headers: { "Content-Type": "application/json" } },
    ),
  );

  await expect(
    deploymentApi.rotateToken(projectId, tokenId, 120),
  ).resolves.toMatchObject({ token: "mcp_rotated_once" });
  expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
    overlap_seconds: 120,
  });
});

test("maps one-time plaintext and sends the deployment rollback contract", async () => {
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          token: {
            id: tokenId,
            project_id: projectId,
            name: "Desktop",
            token_prefix: "mcp_abc",
            created_by: userId,
            created_at: now,
            expires_at: null,
            last_used_at: null,
            revoked_at: null,
            runtime_effect_state: "effective",
            runtime_command_id: null,
            runtime_error_code: null,
          },
          plaintext: "mcp_once_secret",
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    )
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: deploymentId,
          project_id: projectId,
          build_id: buildId,
          status: "pending",
          hostname: "inventory.mcp.example.test",
          endpoint_url: "https://inventory.mcp.example.test/mcp",
          image_ref: "ghcr.io/example/runtime:1",
          image_digest: null,
          manifest_sha256: "a".repeat(64),
          container_id: null,
          container_name: "mcplica-inventory",
          network_name: "mcplica-runtime",
          runtime_version: "1.0.0",
          auth_overlay_sha256: null,
          health_status: null,
          error_code: null,
          error_summary: null,
          created_at: now,
          started_at: null,
          activated_at: null,
          activation_phase: null,
          activation_verified_at: null,
          activation_proof_sha256: null,
          stopped_at: null,
          failed_at: null,
          rollback_eligible: false,
        }),
        {
          status: 202,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );

  await expect(
    deploymentApi.createToken(projectId, { name: "Desktop" }),
  ).resolves.toMatchObject({ token: "mcp_once_secret" });
  await deploymentApi.rollback(projectId, deploymentId);

  expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toEqual({
    target_deployment_id: deploymentId,
  });
});
