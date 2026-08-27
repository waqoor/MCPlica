import { api, jsonBody } from "./client";
import type {
  ModelCatalogItem,
  ModelSettings,
  SystemSettings,
  User,
} from "./contracts";
import { endpointResponses } from "./generated/zod";

type SystemSettingsUpdate = Omit<SystemSettings, "environment">;
type ModelSettingsUpdate = Pick<
  ModelSettings,
  | "analysis_model"
  | "validation_model"
  | "embedding_model"
  | "include_documentation_in_analysis"
>;

export const settingsApi = {
  get: (signal?: AbortSignal) =>
    api<SystemSettings>(
      "/api/v1/settings",
      endpointResponses["get /api/v1/settings"],
      { signal },
    ),
  update: (payload: SystemSettingsUpdate) =>
    api<SystemSettings>(
      "/api/v1/settings",
      endpointResponses["patch /api/v1/settings"],
      {
        method: "PATCH",
        body: jsonBody({
          builders_can_deploy: payload.builders_can_deploy,
          mcp_base_domain: payload.mcp_base_domain,
          build_concurrency: payload.build_concurrency,
          source_retention_days: payload.source_retention_days,
          build_retention_count: payload.build_retention_count,
          max_upload_bytes: payload.max_upload_bytes,
          max_operations_per_project: payload.max_operations_per_project,
          max_document_chunks_per_project:
            payload.max_document_chunks_per_project,
        }),
      },
    ),
  models: (signal?: AbortSignal) =>
    api<ModelSettings>(
      "/api/v1/settings/models",
      endpointResponses["get /api/v1/settings/models"],
      { signal },
    ),
  updateModels: (payload: ModelSettingsUpdate) =>
    api<ModelSettings>(
      "/api/v1/settings/models",
      endpointResponses["put /api/v1/settings/models"],
      {
        method: "PUT",
        body: jsonBody({
          analysis_model: payload.analysis_model,
          validation_model: payload.validation_model,
          embedding_model: payload.embedding_model,
          include_documentation_in_analysis:
            payload.include_documentation_in_analysis,
        }),
      },
    ),
  updateOpenRouter: (apiKey: string) =>
    api<ModelSettings>(
      "/api/v1/settings/openrouter",
      endpointResponses["put /api/v1/settings/openrouter"],
      {
        method: "PUT",
        body: jsonBody({ api_key: apiKey }),
      },
    ),
  testOpenRouter: () =>
    api<{ ok: boolean; message: string }>(
      "/api/v1/settings/openrouter/test",
      endpointResponses["post /api/v1/settings/openrouter/test"],
      { method: "POST" },
    ),
  modelCatalog: (signal?: AbortSignal) =>
    api<ModelCatalogItem[]>(
      "/api/v1/settings/models/catalog",
      endpointResponses["get /api/v1/settings/models/catalog"],
      { signal },
    ),
};

export const userApi = {
  list: (signal?: AbortSignal) =>
    api<User[]>("/api/v1/users", endpointResponses["get /api/v1/users"], {
      signal,
    }),
  create: (payload: {
    email: string;
    display_name: string;
    role: "admin" | "builder";
    password: string;
  }) =>
    api<User>("/api/v1/users", endpointResponses["post /api/v1/users"], {
      method: "POST",
      body: jsonBody(payload),
    }),
  update: (
    userId: string,
    payload: Partial<Pick<User, "display_name" | "role" | "is_active">> & {
      password?: string;
    },
  ) =>
    api<User>(
      `/api/v1/users/${userId}`,
      endpointResponses["patch /api/v1/users/:user_id"],
      {
        method: "PATCH",
        body: jsonBody(payload),
      },
    ),
};
