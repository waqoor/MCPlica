import { api } from "./client";
import type { Readiness } from "./contracts";
import type { components } from "./generated/schema";
import { endpointResponses } from "./generated/zod";

type HealthResponse = components["schemas"]["HealthRead"];
type ReadyResponse = components["schemas"]["ReadinessRead"];

export const systemApi = {
  health: (signal?: AbortSignal) =>
    api<HealthResponse>(
      "/api/v1/health",
      endpointResponses["get /api/v1/health"],
      { signal },
    ),
  readiness: async (signal?: AbortSignal): Promise<Readiness> => {
    const response = await api<ReadyResponse>(
      "/api/v1/ready",
      endpointResponses["get /api/v1/ready"],
      { signal },
    );
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
