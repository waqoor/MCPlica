import { api, download, jsonBody, queryString } from "./client";
import { endpointResponses } from "./generated/zod";
import { BUILD_STATUSES } from "./generated/constants";
import type {
  Build,
  BuildAIRun,
  BuildAdmissionOverview,
  BuildPage,
  BuildMetrics,
  BuildDiff,
  BuildStatus,
  MCPManifest,
  OperationPage,
  OperationExclusion,
  ValidationReport,
} from "./contracts";

export type BuildFilters = {
  project_id?: string;
  status?: BuildStatus;
  page?: number;
  page_size?: number;
};

const buildStatusValues: ReadonlySet<string> = new Set(BUILD_STATUSES);

export function parseBuildStatusFilter(
  value: string | null,
): BuildStatus | undefined {
  return value && buildStatusValues.has(value)
    ? (value as BuildStatus)
    : undefined;
}

export const buildApi = {
  admission: (signal?: AbortSignal) =>
    api<BuildAdmissionOverview>(
      "/api/v1/build-admission",
      endpointResponses["get /api/v1/build-admission"],
      { signal },
    ),
  listAllPage: (filters: BuildFilters = {}, signal?: AbortSignal) =>
    api<BuildPage>(
      `/api/v1/builds${queryString(filters)}`,
      endpointResponses["get /api/v1/builds"],
      { signal },
    ),
  listAll: async (filters: BuildFilters = {}, signal?: AbortSignal) =>
    (await buildApi.listAllPage(filters, signal)).items,
  metrics: (signal?: AbortSignal) =>
    api<BuildMetrics>(
      "/api/v1/builds/metrics",
      endpointResponses["get /api/v1/builds/metrics"],
      { signal },
    ),
  listPage: (
    projectId: string,
    filters: Pick<BuildFilters, "page" | "page_size"> = {},
    signal?: AbortSignal,
  ) =>
    api<BuildPage>(
      `/api/v1/projects/${projectId}/builds${queryString(filters)}`,
      endpointResponses["get /api/v1/projects/:project_id/builds"],
      { signal },
    ),
  list: async (projectId: string, signal?: AbortSignal) =>
    (await buildApi.listPage(projectId, { page_size: 200 }, signal)).items,
  create: (projectId: string) =>
    api<Build>(
      `/api/v1/projects/${projectId}/builds`,
      endpointResponses["post /api/v1/projects/:project_id/builds"],
      {
        method: "POST",
        body: jsonBody({ trigger: "initial" }),
      },
    ),
  get: (buildId: string, signal?: AbortSignal) =>
    api<Build>(
      `/api/v1/builds/${buildId}`,
      endpointResponses["get /api/v1/builds/:build_id"],
      { signal },
    ),
  cancel: (buildId: string) =>
    api<Build>(
      `/api/v1/builds/${buildId}/cancel`,
      endpointResponses["post /api/v1/builds/:build_id/cancel"],
      { method: "POST" },
    ),
  review: (projectId: string) =>
    api<Build>(
      `/api/v1/projects/${projectId}/review`,
      endpointResponses["post /api/v1/projects/:project_id/review"],
      { method: "POST" },
    ),
  rebuild: (projectId: string) =>
    api<Build>(
      `/api/v1/projects/${projectId}/rebuild`,
      endpointResponses["post /api/v1/projects/:project_id/rebuild"],
      { method: "POST" },
    ),
  validation: (buildId: string, signal?: AbortSignal) =>
    api<ValidationReport>(
      `/api/v1/builds/${buildId}/validation`,
      endpointResponses["get /api/v1/builds/:build_id/validation"],
      { signal },
    ),
  diff: (buildId: string, signal?: AbortSignal) =>
    api<BuildDiff>(
      `/api/v1/builds/${buildId}/diff`,
      endpointResponses["get /api/v1/builds/:build_id/diff"],
      { signal },
    ),
  manifest: (buildId: string, signal?: AbortSignal) =>
    api<MCPManifest>(
      `/api/v1/builds/${buildId}/manifest`,
      endpointResponses["get /api/v1/builds/:build_id/manifest"],
      { signal },
    ),
  downloadManifest: (buildId: string, signal?: AbortSignal) =>
    download(`/api/v1/builds/${buildId}/manifest/download`, signal),
  aiRuns: (buildId: string, signal?: AbortSignal) =>
    api<BuildAIRun[]>(
      `/api/v1/builds/${buildId}/ai-runs`,
      endpointResponses["get /api/v1/builds/:build_id/ai-runs"],
      { signal },
    ),
  operations: (
    buildId: string,
    filters: {
      search?: string;
      method?: string;
      scope?: string;
      page?: number;
      page_size?: number;
    } = {},
    signal?: AbortSignal,
  ) =>
    api<OperationPage>(
      `/api/v1/builds/${buildId}/operations${queryString(filters)}`,
      endpointResponses["get /api/v1/builds/:build_id/operations"],
      { signal },
    ),
  exclusions: (projectId: string, signal?: AbortSignal) =>
    api<OperationExclusion[]>(
      `/api/v1/projects/${projectId}/operation-exclusions`,
      endpointResponses[
        "get /api/v1/projects/:project_id/operation-exclusions"
      ],
      { signal },
    ),
  excludeOperation: (projectId: string, operationKey: string, reason: string) =>
    api<OperationExclusion>(
      `/api/v1/projects/${projectId}/operation-exclusions`,
      endpointResponses[
        "post /api/v1/projects/:project_id/operation-exclusions"
      ],
      {
        method: "POST",
        body: jsonBody({ operation_key: operationKey, reason }),
      },
    ),
  removeExclusion: (projectId: string, exclusionId: string) =>
    api<void>(
      `/api/v1/projects/${projectId}/operation-exclusions/${exclusionId}`,
      endpointResponses[
        "delete /api/v1/projects/:project_id/operation-exclusions/:exclusion_id"
      ],
      {
        method: "DELETE",
      },
    ),
  export: (buildId: string, signal?: AbortSignal) =>
    download(`/api/v1/builds/${buildId}/export`, signal),
};
