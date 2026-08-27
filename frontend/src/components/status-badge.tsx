import type { BuildStatus, DeploymentStatus } from "@/api/contracts";
import { titleCase } from "@/lib/format";
import { Badge } from "./ui/badge";

const buildTone: Record<
  BuildStatus,
  "neutral" | "info" | "success" | "warning" | "danger"
> = {
  QUEUED: "neutral",
  INGESTING: "info",
  PARSING: "info",
  INDEXING: "info",
  ANALYZING: "info",
  COMPILING: "info",
  VALIDATING: "warning",
  PACKAGING: "warning",
  READY: "success",
  FAILED: "danger",
  CANCELLED: "neutral",
};

const deploymentTone: Record<
  DeploymentStatus,
  "neutral" | "info" | "success" | "warning" | "danger"
> = {
  pending: "neutral",
  deploying: "info",
  healthcheck: "warning",
  running: "success",
  unhealthy: "danger",
  stopping: "warning",
  stopped: "neutral",
  failed: "danger",
};

export function BuildStatusBadge({ status }: { status: BuildStatus }) {
  return <Badge tone={buildTone[status]}>{titleCase(status)}</Badge>;
}

export function DeploymentStatusBadge({
  status,
}: {
  status: DeploymentStatus;
}) {
  return <Badge tone={deploymentTone[status]}>{titleCase(status)}</Badge>;
}

export function HealthBadge({ status }: { status: string | null | undefined }) {
  const normalized = status?.toLowerCase() ?? "unknown";
  const tone = ["healthy", "ready", "ok", "running"].includes(normalized)
    ? "success"
    : ["unhealthy", "failed", "unavailable"].includes(normalized)
      ? "danger"
      : normalized === "degraded"
        ? "warning"
        : "neutral";
  return <Badge tone={tone}>{titleCase(normalized)}</Badge>;
}
