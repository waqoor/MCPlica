import { api, jsonBody } from "./client";
import type {
  CleanupJob,
  Page,
  ProjectSource,
  SourceConfigurationDiscovery,
  SourceKind,
  SourceVersion,
  SourceVersionMetadata,
} from "./contracts";
import type { components } from "./generated/schema";
import { endpointResponses } from "./generated/zod";

type SourceCreationWire = components["schemas"]["SourceCreationRead"];

type UrlSourcePayload = {
  source_id: string;
  name: string;
  kind: SourceKind;
  source_url: string;
  is_primary?: boolean;
};

type UploadSourcePayload = {
  source_id: string;
  name: string;
  kind: SourceKind;
  file: File;
  is_primary?: boolean;
};

function uploadForm(payload: UploadSourcePayload): FormData {
  const body = new FormData();
  body.set("source_id", payload.source_id);
  body.set("name", payload.name);
  body.set("kind", payload.kind);
  body.set("is_primary", String(payload.is_primary ?? false));
  body.set("file", payload.file);
  return body;
}

function versionsPage(
  projectId: string,
  sourceId: string,
  filters: { page?: number; page_size?: number } = {},
  signal?: AbortSignal,
) {
  const params = new URLSearchParams();
  if (filters.page) params.set("page", String(filters.page));
  if (filters.page_size) params.set("page_size", String(filters.page_size));
  const suffix = params.size ? `?${params.toString()}` : "";
  return api<Page<SourceVersion>>(
    `/api/v1/projects/${projectId}/sources/${sourceId}/versions${suffix}`,
    endpointResponses[
      "get /api/v1/projects/:project_id/sources/:source_id/versions"
    ],
    { signal },
  );
}

async function versions(
  projectId: string,
  sourceId: string,
  signal?: AbortSignal,
) {
  return (await versionsPage(projectId, sourceId, { page_size: 100 }, signal))
    .items;
}

function versionMetadata(versionId: string, signal?: AbortSignal) {
  return api<SourceVersionMetadata>(
    `/api/v1/source-versions/${versionId}/metadata`,
    endpointResponses["get /api/v1/source-versions/:version_id/metadata"],
    { signal },
  );
}

export const sourceApi = {
  configuration: (projectId: string, signal?: AbortSignal) =>
    api<SourceConfigurationDiscovery>(
      `/api/v1/projects/${projectId}/source-configuration`,
      endpointResponses[
        "get /api/v1/projects/:project_id/source-configuration"
      ],
      { signal },
    ),
  listPage: (
    projectId: string,
    filters: { page?: number; page_size?: number } = {},
    signal?: AbortSignal,
  ) => {
    const params = new URLSearchParams();
    if (filters.page) params.set("page", String(filters.page));
    if (filters.page_size) params.set("page_size", String(filters.page_size));
    const suffix = params.size ? `?${params.toString()}` : "";
    return api<Page<ProjectSource>>(
      `/api/v1/projects/${projectId}/sources${suffix}`,
      endpointResponses["get /api/v1/projects/:project_id/sources"],
      { signal },
    );
  },
  list: async (projectId: string, signal?: AbortSignal) =>
    (await sourceApi.listPage(projectId, { page_size: 100 }, signal)).items,
  createFromUrl: async (projectId: string, payload: UrlSourcePayload) => {
    const created = await api<SourceCreationWire>(
      `/api/v1/projects/${projectId}/sources/url`,
      endpointResponses["post /api/v1/projects/:project_id/sources/url"],
      {
        method: "POST",
        body: jsonBody(payload),
      },
    );
    return {
      ...created.source,
      latest_version: created.version,
      version_count: 1,
    };
  },
  createFromUpload: async (projectId: string, payload: UploadSourcePayload) => {
    const created = await api<SourceCreationWire>(
      `/api/v1/projects/${projectId}/sources/upload`,
      endpointResponses["post /api/v1/projects/:project_id/sources/upload"],
      {
        method: "POST",
        body: uploadForm(payload),
      },
    );
    return {
      ...created.source,
      latest_version: created.version,
      version_count: 1,
    };
  },
  update: (
    projectId: string,
    sourceId: string,
    payload: { name?: string; is_primary?: boolean },
  ) =>
    api<ProjectSource>(
      `/api/v1/projects/${projectId}/sources/${sourceId}`,
      endpointResponses[
        "patch /api/v1/projects/:project_id/sources/:source_id"
      ],
      {
        method: "PATCH",
        body: jsonBody(payload),
      },
    ),
  remove: (projectId: string, sourceId: string) =>
    api<CleanupJob>(
      `/api/v1/projects/${projectId}/sources/${sourceId}`,
      endpointResponses[
        "delete /api/v1/projects/:project_id/sources/:source_id"
      ],
      { method: "DELETE" },
    ),
  addVersion: (projectId: string, sourceId: string, file: File) => {
    const body = new FormData();
    body.set("file", file);
    return api<SourceVersion>(
      `/api/v1/projects/${projectId}/sources/${sourceId}/versions`,
      endpointResponses[
        "post /api/v1/projects/:project_id/sources/:source_id/versions"
      ],
      {
        method: "POST",
        body,
      },
    );
  },
  refresh: (projectId: string, sourceId: string) =>
    api<SourceVersion>(
      `/api/v1/projects/${projectId}/sources/${sourceId}/refresh`,
      endpointResponses[
        "post /api/v1/projects/:project_id/sources/:source_id/refresh"
      ],
      {
        method: "POST",
      },
    ),
  versions,
  versionsPage,
  versionMetadata,
};
