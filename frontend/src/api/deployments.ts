import { api, jsonBody } from "./client";
import type {
  Deployment,
  McpAccessConfig,
  McpAccessToken,
  McpAuthMode,
} from "./contracts";

type McpAuthConfigWire = {
  project_id: string;
  mode: McpAuthMode;
  issuer_url: string | null;
  audiences: string[];
  required_scopes: string[];
  updated_at: string;
};

type McpAccessWire = {
  auth_config: McpAuthConfigWire | null;
  tokens: McpAccessToken[];
};

type McpTokenIssuedWire = {
  token: McpAccessToken;
  plaintext: string;
};

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
  return {
    project_id: auth?.project_id ?? projectId,
    mode,
    issuer_url: auth?.issuer_url ?? null,
    audiences: auth?.audiences ?? [],
    required_scopes: auth?.required_scopes ?? [],
    updated_at: auth?.updated_at ?? null,
    development_mode: mode === "disabled_dev",
    configured,
    tokens: response.tokens,
  };
}

function normalizeIssued(response: McpTokenIssuedWire): McpAccessToken {
  return { ...response.token, token: response.plaintext };
}

export const deploymentApi = {
  list: (projectId: string, signal?: AbortSignal) =>
    api<Deployment[]>(`/api/v1/projects/${projectId}/deployments`, { signal }),
  get: (deploymentId: string, signal?: AbortSignal) =>
    api<Deployment>(`/api/v1/deployments/${deploymentId}`, { signal }),
  deploy: (projectId: string, buildId: string) =>
    api<Deployment>(`/api/v1/projects/${projectId}/deployments`, {
      method: "POST",
      body: jsonBody({ build_id: buildId }),
    }),
  stop: (deploymentId: string) =>
    api<Deployment>(`/api/v1/deployments/${deploymentId}/stop`, {
      method: "POST",
    }),
  restart: (deploymentId: string) =>
    api<Deployment>(`/api/v1/deployments/${deploymentId}/restart`, {
      method: "POST",
    }),
  rollback: (projectId: string, targetDeploymentId: string) =>
    api<Deployment>(`/api/v1/projects/${projectId}/rollback`, {
      method: "POST",
      body: jsonBody({ target_deployment_id: targetDeploymentId }),
    }),
  access: async (projectId: string, signal?: AbortSignal) =>
    normalizeAccess(
      projectId,
      await api<McpAccessWire>(`/api/v1/projects/${projectId}/mcp-access`, {
        signal,
      }),
    ),
  setAuthMode: (
    projectId: string,
    payload: {
      mode: McpAuthMode;
      issuer_url?: string;
      audiences?: string[];
      required_scopes?: string[];
    },
  ) =>
    api<McpAuthConfigWire>(
      `/api/v1/projects/${projectId}/mcp-access/auth-mode`,
      {
        method: "PUT",
        body: jsonBody(payload),
      },
    ),
  createToken: (
    projectId: string,
    payload: { name: string; expires_at?: string | null },
  ) =>
    api<McpTokenIssuedWire>(`/api/v1/projects/${projectId}/mcp-access/tokens`, {
      method: "POST",
      body: jsonBody(payload),
    }).then(normalizeIssued),
  rotateToken: (projectId: string, tokenId: string, overlapSeconds = 300) =>
    api<McpTokenIssuedWire>(
      `/api/v1/projects/${projectId}/mcp-access/tokens/${tokenId}/rotate`,
      {
        method: "POST",
        body: jsonBody({ overlap_seconds: overlapSeconds }),
      },
    ).then(normalizeIssued),
  revokeToken: (projectId: string, tokenId: string) =>
    api<void>(`/api/v1/projects/${projectId}/mcp-access/tokens/${tokenId}`, {
      method: "DELETE",
    }),
};
