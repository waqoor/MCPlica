import { api, download, jsonBody, queryString } from "./client";
import type {
  Build,
  BuildDiff,
  Operation,
  ValidationReport,
} from "./contracts";

export type BuildFilters = {
  project_id?: string;
  status?: string;
  page?: number;
  page_size?: number;
};

export const buildApi = {
  listAll: (filters: BuildFilters = {}, signal?: AbortSignal) =>
    api<Build[]>(`/api/v1/builds${queryString(filters)}`, { signal }),
  list: (projectId: string, signal?: AbortSignal) =>
    api<Build[]>(`/api/v1/projects/${projectId}/builds`, { signal }),
  create: (projectId: string) =>
    api<Build>(`/api/v1/projects/${projectId}/builds`, {
      method: "POST",
      body: jsonBody({ trigger: "initial" }),
    }),
  get: (buildId: string, signal?: AbortSignal) =>
    api<Build>(`/api/v1/builds/${buildId}`, { signal }),
  cancel: (buildId: string) =>
    api<Build>(`/api/v1/builds/${buildId}/cancel`, { method: "POST" }),
  review: (projectId: string) =>
    api<Build>(`/api/v1/projects/${projectId}/review`, { method: "POST" }),
  rebuild: (projectId: string) =>
    api<Build>(`/api/v1/projects/${projectId}/rebuild`, { method: "POST" }),
  validation: (buildId: string, signal?: AbortSignal) =>
    api<ValidationReport>(`/api/v1/builds/${buildId}/validation`, { signal }),
  diff: (buildId: string, signal?: AbortSignal) =>
    api<BuildDiff>(`/api/v1/builds/${buildId}/diff`, { signal }),
  operations: (buildId: string, signal?: AbortSignal) =>
    api<Operation[]>(`/api/v1/builds/${buildId}/operations`, { signal }),
  excludeOperation: (projectId: string, operationKey: string, reason: string) =>
    api<void>(`/api/v1/projects/${projectId}/operation-exclusions`, {
      method: "POST",
      body: jsonBody({ operation_key: operationKey, reason }),
    }),
  removeExclusion: (projectId: string, exclusionId: string) =>
    api<void>(
      `/api/v1/projects/${projectId}/operation-exclusions/${exclusionId}`,
      {
        method: "DELETE",
      },
    ),
  export: (buildId: string, signal?: AbortSignal) =>
    download(`/api/v1/builds/${buildId}/export`, signal),
};
