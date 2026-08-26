import { afterEach, expect, test, vi } from "vitest";
import { deploymentApi } from "./deployments";

afterEach(() => vi.restoreAllMocks());

test("normalizes MCP access without weakening static-token readiness", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        auth_config: {
          project_id: "project-1",
          mode: "static_bearer",
          issuer_url: null,
          audiences: [],
          required_scopes: [],
          updated_at: "2026-08-26T10:00:00Z",
        },
        tokens: [],
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );

  await expect(deploymentApi.access("project-1")).resolves.toMatchObject({
    project_id: "project-1",
    mode: "static_bearer",
    configured: false,
    tokens: [],
  });
});

test("maps one-time plaintext and sends the deployment rollback contract", async () => {
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          token: {
            id: "token-1",
            project_id: "project-1",
            name: "Desktop",
            token_prefix: "mcp_abc",
            created_at: "2026-08-26T10:00:00Z",
            expires_at: null,
            last_used_at: null,
            revoked_at: null,
          },
          plaintext: "mcp_once_secret",
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    )
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ id: "deployment-new" }), {
        status: 202,
        headers: { "Content-Type": "application/json" },
      }),
    );

  await expect(
    deploymentApi.createToken("project-1", { name: "Desktop" }),
  ).resolves.toMatchObject({ token: "mcp_once_secret" });
  await deploymentApi.rollback("project-1", "deployment-old");

  expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toEqual({
    target_deployment_id: "deployment-old",
  });
});
