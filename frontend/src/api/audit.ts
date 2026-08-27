import { api, queryString } from "./client";
import type { AuditEvent, Page } from "./contracts";
import { endpointResponses } from "./generated/zod";

export type AuditFilters = {
  actor?: string;
  project_id?: string;
  event_type?: string;
  from?: string;
  to?: string;
  page?: number;
  page_size?: number;
};

export const auditApi = {
  list: (filters: AuditFilters = {}, signal?: AbortSignal) =>
    api<Page<AuditEvent>>(
      `/api/v1/audit${queryString(filters)}`,
      endpointResponses["get /api/v1/audit"],
      { signal },
    ),
};
