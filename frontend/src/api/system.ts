import { api } from "./client";
import type { Readiness } from "./contracts";

type ReadyResponse = {
  ready: boolean;
  dependencies: Record<string, boolean>;
};

export const systemApi = {
  health: (signal?: AbortSignal) =>
    api<{ status: string; service: string }>("/api/v1/health", { signal }),
  readiness: async (signal?: AbortSignal): Promise<Readiness> => {
    const response = await api<ReadyResponse>("/api/v1/ready", { signal });
    const checks = Object.entries(response.dependencies).map(
      ([name, ready]) => ({
        name,
        status: ready ? ("ready" as const) : ("unavailable" as const),
      }),
    );
    const optionalDown = checks.some(
      (check) =>
        ["milvus", "openrouter"].includes(check.name) &&
        check.status !== "ready",
    );
    return {
      status: response.ready
        ? optionalDown
          ? "degraded"
          : "ready"
        : "unavailable",
      checks,
    };
  },
};
