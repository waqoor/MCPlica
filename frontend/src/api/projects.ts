import { api, jsonBody } from "./client";
import type { Project } from "./contracts";

export type CreateProject = Pick<Project, "name" | "slug"> & {
  description?: string;
  default_base_url?: string;
};
export type UpdateProject = Partial<
  Pick<Project, "name" | "description" | "is_enabled" | "default_base_url">
>;

export const projectApi = {
  list: (signal?: AbortSignal) =>
    api<Project[]>("/api/v1/projects", { signal }),
  get: (projectId: string, signal?: AbortSignal) =>
    api<Project>(`/api/v1/projects/${projectId}`, { signal }),
  create: (payload: CreateProject) =>
    api<Project>("/api/v1/projects", {
      method: "POST",
      body: jsonBody(payload),
    }),
  update: (projectId: string, payload: UpdateProject) =>
    api<Project>(`/api/v1/projects/${projectId}`, {
      method: "PATCH",
      body: jsonBody(payload),
    }),
  remove: (projectId: string) =>
    api<void>(`/api/v1/projects/${projectId}`, { method: "DELETE" }),
};

export type { Project };
