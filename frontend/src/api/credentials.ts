import { api, jsonBody } from "./client";
import type { Credential, SecuritySchemeDiscovery } from "./contracts";
import { endpointResponses } from "./generated/zod";

export type CredentialScheme =
  | "bearer"
  | "api_key_header"
  | "api_key_query"
  | "basic"
  | "oauth2_client_credentials"
  | "static_headers";

export function credentialSchemeForSource(
  scheme: SecuritySchemeDiscovery,
): CredentialScheme | null {
  if (scheme.type === "http_bearer") return "bearer";
  if (scheme.type === "http_basic") return "basic";
  if (scheme.type === "oauth2_client_credentials")
    return "oauth2_client_credentials";
  if (scheme.type === "static_headers") return "static_headers";
  if (scheme.type === "api_key" && scheme.location === "header")
    return "api_key_header";
  if (scheme.type === "api_key" && scheme.location === "query")
    return "api_key_query";
  return null;
}

export type CredentialSecretInput = {
  token?: string;
  value?: string;
  username?: string;
  password?: string;
  client_id?: string;
  client_secret?: string;
  headers?: Record<string, string>;
};

export type CredentialSecretFields = {
  value: string;
  identity?: string;
  scope?: string;
  headerName?: string;
  securityScheme?: string;
  tokenAuthMethod?: "client_secret_basic" | "client_secret_post";
};

export function credentialSecretFor(
  scheme: CredentialScheme,
  fields: CredentialSecretFields,
): Pick<CredentialInput, "secret" | "metadata"> {
  const binding: Record<string, string> = {};
  if (fields.securityScheme) binding.security_scheme = fields.securityScheme;
  switch (scheme) {
    case "bearer":
      return { secret: { token: fields.value }, metadata: binding };
    case "api_key_header":
    case "api_key_query":
      return {
        secret: { value: fields.value },
        metadata: { ...binding, name: fields.headerName ?? "" },
      };
    case "basic":
      return {
        secret: {
          username: fields.identity ?? "",
          password: fields.value,
        },
        metadata: binding,
      };
    case "oauth2_client_credentials":
      return {
        secret: {
          client_id: fields.identity ?? "",
          client_secret: fields.value,
        },
        metadata: {
          ...binding,
          ...(fields.scope ? { scope: fields.scope } : {}),
          token_auth_method: fields.tokenAuthMethod ?? "client_secret_basic",
        },
      };
    case "static_headers":
      return {
        secret: { headers: { [fields.headerName ?? ""]: fields.value } },
        metadata: binding,
      };
  }
}

export type CredentialInput = {
  name: string;
  scheme_type: CredentialScheme;
  secret: CredentialSecretInput;
  metadata?: Record<string, string>;
};

export const credentialApi = {
  list: (projectId: string, signal?: AbortSignal) =>
    api<Credential[]>(
      `/api/v1/projects/${projectId}/credentials`,
      endpointResponses["get /api/v1/projects/:project_id/credentials"],
      { signal },
    ),
  create: (projectId: string, payload: CredentialInput) =>
    api<Credential>(
      `/api/v1/projects/${projectId}/credentials`,
      endpointResponses["post /api/v1/projects/:project_id/credentials"],
      {
        method: "POST",
        body: jsonBody(payload),
      },
    ),
  rotate: (
    projectId: string,
    credentialId: string,
    payload: Pick<CredentialInput, "secret" | "metadata">,
  ) =>
    api<Credential>(
      `/api/v1/projects/${projectId}/credentials/${credentialId}/rotate`,
      endpointResponses[
        "post /api/v1/projects/:project_id/credentials/:credential_id/rotate"
      ],
      {
        method: "POST",
        body: jsonBody(payload),
      },
    ),
  revoke: (projectId: string, credentialId: string) =>
    api<Credential>(
      `/api/v1/projects/${projectId}/credentials/${credentialId}`,
      endpointResponses[
        "delete /api/v1/projects/:project_id/credentials/:credential_id"
      ],
      {
        method: "DELETE",
      },
    ),
};
