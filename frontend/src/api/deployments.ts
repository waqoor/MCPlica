import { api, jsonBody, queryString } from "./client";
import type {
  Deployment,
  DeploymentPage,
  McpAccessConfig,
  McpAccessToken,
  McpAuthModePayload,
} from "./contracts";
import type { components } from "./generated/schema";
import { endpointResponses } from "./generated/zod";

type McpAuthConfigWire = components["schemas"]["MCPAuthConfigRead"];
type McpAccessWire = components["schemas"]["MCPAccessRead"];
type McpTokenIssuedWire = components["schemas"]["MCPAccessTokenIssued"];
type McpAccessStatusWire = components["schemas"]["MCPAccessStatusRead"];

function activeToken(token: McpAccessToken) {
  return (
    !token.revoked_at &&
    (!token.expires_at || Date.parse(token.expires_at) > Date.now())
  );
}

function normalizeAccess(
  projectId: string,
  response: McpAccessWire,
): McpAccessConfig {
  const auth = response.auth_config;
  const mode = auth?.mode ?? "static_bearer";
  const configured = Boolean(
    auth && (mode !== "static_bearer" || response.tokens.some(activeToken)),
  );
  const jwksUrl = auth?.metadata.jwks_url;
  const algorithms = auth?.metadata.allowed_algorithms;
  return {
    project_id: auth?.project_id ?? projectId,
    mode,
    issuer_url: auth?.issuer_url ?? null,
    jwks_url: typeof jwksUrl === "string" ? jwksUrl : null,
    audiences: auth?.audiences ?? [],
    required_scopes: auth?.required_scopes ?? [],
    allowed_algorithms:
      Array.isArray(algorithms) &&
      algorithms.every((value): value is string => typeof value === "string")
        ? algorithms
        : [],
    updated_at: auth?.updated_at ?? null,
    development_mode: mode === "disabled_dev",
    configured,
    tokens: response.tokens,
    runtime_effect_state: auth?.runtime_effect_state ?? "effective",
    runtime_command_id: auth?.runtime_command_id ?? null,
    runtime_error_code: auth?.runtime_error_code ?? null,
  };
}

function normalizeIssued(response: McpTokenIssuedWire): McpAccessToken {
  return { ...response.token, token: response.plaintext };
}

async function loadAccess(
  projectId: string,
  signal?: AbortSignal,
): Promise<McpAccessWire> {
  let page = 1;
  let first: McpAccessWire | null = null;
  const tokens: Array<McpAccessWire["tokens"][number]> = [];
  while (true) {
    const response = await api<McpAccessWire>(
      `/api/v1/projects/${projectId}/mcp-access${queryString({ page, page_size: 200 })}`,
      endpointResponses["get /api/v1/projects/:project_id/mcp-access"],
      { signal },
    );
    if (response.page !== page || response.page_size !== 200) {
      throw new Error(
        "The server returned inconsistent access-token pagination metadata.",
      );
    }
    first ??= response;
    tokens.push(...response.tokens);
    if (tokens.length >= response.total) return { ...first, tokens };
    if (response.tokens.length === 0) {
      throw new Error("The server returned an incomplete access-token page.");
    }
    page += 1;
  }
}

export const deploymentApi = {
  listPage: (
    projectId: string,
    filters: { page?: number; page_size?: number } = {},
    signal?: AbortSignal,
  ) =>
    api<DeploymentPage>(
      `/api/v1/projects/${projectId}/deployments${queryString(filters)}`,
      endpointResponses["get /api/v1/projects/:project_id/deployments"],
      { signal },
    ),
  list: async (projectId: string, signal?: AbortSignal) =>
    (await deploymentApi.listPage(projectId, { page_size: 200 }, signal)).items,
  get: (deploymentId: string, signal?: AbortSignal) =>
    api<Deployment>(
      `/api/v1/deployments/${deploymentId}`,
      endpointResponses["get /api/v1/deployments/:deployment_id"],
      { signal },
    ),
  deploy: (projectId: string, buildId: string) =>
    api<Deployment>(
      `/api/v1/projects/${projectId}/deployments`,
      endpointResponses["post /api/v1/projects/:project_id/deployments"],
      {
        method: "POST",
        body: jsonBody({ build_id: buildId }),
      },
    ),
  stop: (deploymentId: string) =>
    api<Deployment>(
      `/api/v1/deployments/${deploymentId}/stop`,
      endpointResponses["post /api/v1/deployments/:deployment_id/stop"],
      { method: "POST" },
    ),
  restart: (deploymentId: string) =>
    api<Deployment>(
      `/api/v1/deployments/${deploymentId}/restart`,
      endpointResponses["post /api/v1/deployments/:deployment_id/restart"],
      { method: "POST" },
    ),
  rollback: (projectId: string, targetDeploymentId: string) =>
    api<Deployment>(
      `/api/v1/projects/${projectId}/rollback`,
      endpointResponses["post /api/v1/projects/:project_id/rollback"],
      {
        method: "POST",
        body: jsonBody({ target_deployment_id: targetDeploymentId }),
      },
    ),
  access: async (projectId: string, signal?: AbortSignal) =>
    normalizeAccess(projectId, await loadAccess(projectId, signal)),
  accessStatus: async (
    projectId: string,
    signal?: AbortSignal,
  ): Promise<McpAccessConfig> => {
    const status = await api<McpAccessStatusWire>(
      `/api/v1/projects/${projectId}/mcp-access/status`,
      endpointResponses["get /api/v1/projects/:project_id/mcp-access/status"],
      { signal },
    );
    return {
      project_id: status.project_id,
      mode: status.mode ?? "static_bearer",
      issuer_url: null,
      jwks_url: null,
      audiences: [],
      required_scopes: [],
      allowed_algorithms: [],
      updated_at: null,
      configured: status.configured,
      runtime_effect_state: status.runtime_effect_state,
      runtime_command_id: status.runtime_command_id,
      runtime_error_code: status.runtime_error_code,
      remediation: status.remediation,
    };
  },
  setAuthMode: (projectId: string, payload: McpAuthModePayload) =>
    api<McpAuthConfigWire>(
      `/api/v1/projects/${projectId}/mcp-access/auth-mode`,
      endpointResponses[
        "put /api/v1/projects/:project_id/mcp-access/auth-mode"
      ],
      {
        method: "PUT",
        body: jsonBody(payload),
      },
    ),
  createToken: (
    projectId: string,
    payload: { name: string; expires_at?: string | null },
  ) =>
    api<McpTokenIssuedWire>(
      `/api/v1/projects/${projectId}/mcp-access/tokens`,
      endpointResponses["post /api/v1/projects/:project_id/mcp-access/tokens"],
      {
        method: "POST",
        body: jsonBody(payload),
      },
    ).then(normalizeIssued),
  rotateToken: (projectId: string, tokenId: string, overlapSeconds = 300) =>
    api<McpTokenIssuedWire>(
      `/api/v1/projects/${projectId}/mcp-access/tokens/${tokenId}/rotate`,
      endpointResponses[
        "post /api/v1/projects/:project_id/mcp-access/tokens/:token_id/rotate"
      ],
      {
        method: "POST",
        body: jsonBody({ overlap_seconds: overlapSeconds }),
      },
    ).then(normalizeIssued),
  revokeToken: (projectId: string, tokenId: string) =>
    api<McpAccessToken>(
      `/api/v1/projects/${projectId}/mcp-access/tokens/${tokenId}`,
      endpointResponses[
        "delete /api/v1/projects/:project_id/mcp-access/tokens/:token_id"
      ],
      {
        method: "DELETE",
      },
    ),
};
