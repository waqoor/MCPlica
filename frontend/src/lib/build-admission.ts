import type {
  Build,
  BuildAdmissionOverview,
  BuildStatus,
} from "@/api/contracts";

const TERMINAL_BUILD_STATUSES = new Set<BuildStatus>([
  "READY",
  "FAILED",
  "CANCELLED",
]);

export function buildAdmissionLabel(
  build: Pick<Build, "id" | "status">,
  overview: BuildAdmissionOverview | undefined,
): string {
  if (TERMINAL_BUILD_STATUSES.has(build.status)) return "Released";
  const entry = overview?.entries.find((item) => item.build_id === build.id);
  if (entry?.state === "waiting") {
    return entry.position ? `Queue #${entry.position}` : "Queued";
  }
  if (entry?.state === "admitted") return "Admitted";
  if (entry?.state === "running") return "Permit active";
  return build.status === "QUEUED" ? "Awaiting admission" : "Recovering permit";
}
