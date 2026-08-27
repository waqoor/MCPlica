import { api, jsonBody, queryString } from "./client";
import type { CleanupJob, Project, ProjectJourney } from "./contracts";
import { endpointResponses } from "./generated/zod";

export type CreateProject = Pick<Project, "name" | "slug"> & {
  description?: string;
  default_base_url?: string;
};
export type UpdateProject = Partial<
  Pick<
    Project,
    | "name"
    | "description"
    | "is_enabled"
    | "default_base_url"
    | "active_server_ref"
    | "server_mappings"
  >
>;

export const projectApi = {
  list: (signal?: AbortSignal) =>
    api<Project[]>(
      "/api/v1/projects",
      endpointResponses["get /api/v1/projects"],
      {
        signal,
      },
    ),
  get: (projectId: string, signal?: AbortSignal) =>
    api<Project>(
      `/api/v1/projects/${projectId}`,
      endpointResponses["get /api/v1/projects/:project_id"],
      { signal },
    ),
  journey: (projectId: string, buildId?: string | null, signal?: AbortSignal) =>
    api<ProjectJourney>(
      `/api/v1/projects/${projectId}/journey${queryString({ build_id: buildId ?? undefined })}`,
      endpointResponses["get /api/v1/projects/:project_id/journey"],
      { signal },
    ),
  create: (payload: CreateProject) =>
    api<Project>(
      "/api/v1/projects",
      endpointResponses["post /api/v1/projects"],
      {
        method: "POST",
        body: jsonBody(payload),
      },
    ),
  update: (projectId: string, payload: UpdateProject) =>
    api<Project>(
      `/api/v1/projects/${projectId}`,
      endpointResponses["patch /api/v1/projects/:project_id"],
      {
        method: "PATCH",
        body: jsonBody(payload),
      },
    ),
  remove: (projectId: string) =>
    api<CleanupJob>(
      `/api/v1/projects/${projectId}`,
      endpointResponses["delete /api/v1/projects/:project_id"],
      { method: "DELETE" },
    ),
};

export type { Project };
