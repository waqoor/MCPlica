import { api, jsonBody } from "./client";
import type { ProjectSource, SourceKind, SourceVersion } from "./contracts";

type UrlSourcePayload = {
  name: string;
  kind: SourceKind;
  source_url: string;
  is_primary?: boolean;
};

type UploadSourcePayload = {
  name: string;
  kind: SourceKind;
  file: File;
  is_primary?: boolean;
};

function uploadForm(payload: UploadSourcePayload): FormData {
  const body = new FormData();
  body.set("file", payload.file);
  return body;
}

function versions(projectId: string, sourceId: string, signal?: AbortSignal) {
  return api<SourceVersion[]>(
    `/api/v1/projects/${projectId}/sources/${sourceId}/versions`,
    { signal },
  );
}

async function hydrateSourceVersions(
  projectId: string,
  sources: ProjectSource[],
  signal?: AbortSignal,
): Promise<ProjectSource[]> {
  const hydrated = new Array<ProjectSource>(sources.length);
  let nextIndex = 0;
  const worker = async () => {
    while (nextIndex < sources.length) {
      const index = nextIndex++;
      const source = sources[index];
      const sourceVersions = await versions(projectId, source.id, signal);
      hydrated[index] = {
        ...source,
        latest_version: sourceVersions[0] ?? null,
        version_count: sourceVersions.length,
      };
    }
  };
  await Promise.all(
    Array.from({ length: Math.min(4, sources.length) }, () => worker()),
  );
  return hydrated;
}

export const sourceApi = {
  list: async (projectId: string, signal?: AbortSignal) => {
    const sources = await api<ProjectSource[]>(
      `/api/v1/projects/${projectId}/sources`,
      { signal },
    );
    return hydrateSourceVersions(projectId, sources, signal);
  },
  createFromUrl: async (projectId: string, payload: UrlSourcePayload) => {
    const source = await api<ProjectSource>(
      `/api/v1/projects/${projectId}/sources`,
      {
        method: "POST",
        body: jsonBody({ ...payload, origin_type: "url" }),
      },
    );
    const version = await api<SourceVersion>(
      `/api/v1/projects/${projectId}/sources/${source.id}/refresh`,
      { method: "POST" },
    );
    return { ...source, latest_version: version, version_count: 1 };
  },
  createFromUpload: async (projectId: string, payload: UploadSourcePayload) => {
    const source = await api<ProjectSource>(
      `/api/v1/projects/${projectId}/sources`,
      {
        method: "POST",
        body: jsonBody({
          name: payload.name,
          kind: payload.kind,
          origin_type: "upload",
          is_primary: payload.is_primary ?? false,
        }),
      },
    );
    const version = await api<SourceVersion>(
      `/api/v1/projects/${projectId}/sources/${source.id}/versions`,
      {
        method: "POST",
        body: uploadForm(payload),
      },
    );
    return { ...source, latest_version: version, version_count: 1 };
  },
  addVersion: (projectId: string, sourceId: string, file: File) => {
    const body = new FormData();
    body.set("file", file);
    return api<SourceVersion>(
      `/api/v1/projects/${projectId}/sources/${sourceId}/versions`,
      {
        method: "POST",
        body,
      },
    );
  },
  refresh: (projectId: string, sourceId: string) =>
    api<SourceVersion>(
      `/api/v1/projects/${projectId}/sources/${sourceId}/refresh`,
      {
        method: "POST",
      },
    ),
  versions,
  versionMetadata: (versionId: string, signal?: AbortSignal) =>
    api<SourceVersion>(`/api/v1/source-versions/${versionId}/metadata`, {
      signal,
    }),
};
