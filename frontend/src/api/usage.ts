import { api, queryString } from "./client";
import type { BuildAIRun, ModelUsage, Page } from "./contracts";
import { endpointResponses } from "./generated/zod";

export type UsageFilters = {
  from?: string;
  to?: string;
};

export type UsageLogFilters = UsageFilters & {
  model: string;
  page?: number;
  page_size?: number;
};

export const usageApi = {
  byModel: (filters: UsageFilters = {}, signal?: AbortSignal) =>
    api<ModelUsage[]>(
      `/api/v1/usage/by-model${queryString(filters)}`,
      endpointResponses["get /api/v1/usage/by-model"],
      { signal },
    ),
  logs: (filters: UsageLogFilters, signal?: AbortSignal) =>
    api<Page<BuildAIRun>>(
      `/api/v1/usage/logs${queryString(filters)}`,
      endpointResponses["get /api/v1/usage/logs"],
      { signal },
    ),
};
