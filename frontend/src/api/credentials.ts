import { api, jsonBody } from "./client";
import type { Credential } from "./contracts";

export type CredentialScheme =
  | "bearer"
  | "api_key_header"
  | "api_key_query"
  | "basic"
  | "oauth2_client_credentials"
  | "static_headers";

export type CredentialSecretInput = {
  token?: string;
  value?: string;
  username?: string;
  password?: string;
  client_id?: string;
  client_secret?: string;
  token_url?: string;
  scope?: string;
  headers?: Record<string, string>;
};

export type CredentialSecretFields = {
  value: string;
  identity?: string;
  tokenUrl?: string;
  scope?: string;
  headerName?: string;
};

export function credentialSecretFor(
  scheme: CredentialScheme,
  fields: CredentialSecretFields,
): Pick<CredentialInput, "secret" | "metadata"> {
  switch (scheme) {
    case "bearer":
      return { secret: { token: fields.value } };
    case "api_key_header":
    case "api_key_query":
      return {
        secret: { value: fields.value },
        metadata: { name: fields.headerName ?? "" },
      };
    case "basic":
      return {
        secret: {
          username: fields.identity ?? "",
          password: fields.value,
        },
      };
    case "oauth2_client_credentials":
      return {
        secret: {
          client_id: fields.identity ?? "",
          client_secret: fields.value,
          token_url: fields.tokenUrl ?? "",
          ...(fields.scope ? { scope: fields.scope } : {}),
        },
      };
    case "static_headers":
      return {
        secret: { headers: { [fields.headerName ?? ""]: fields.value } },
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
    api<Credential[]>(`/api/v1/projects/${projectId}/credentials`, { signal }),
  create: (projectId: string, payload: CredentialInput) =>
    api<Credential>(`/api/v1/projects/${projectId}/credentials`, {
      method: "POST",
      body: jsonBody(payload),
    }),
  rotate: (
    projectId: string,
    credentialId: string,
    secret: CredentialSecretInput,
  ) =>
    api<Credential>(
      `/api/v1/projects/${projectId}/credentials/${credentialId}/rotate`,
      {
        method: "POST",
        body: jsonBody({ secret }),
      },
    ),
  revoke: (projectId: string, credentialId: string) =>
    api<Credential>(
      `/api/v1/projects/${projectId}/credentials/${credentialId}`,
      {
        method: "DELETE",
      },
    ),
};
