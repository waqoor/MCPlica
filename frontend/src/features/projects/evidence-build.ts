import type { Build } from "@/api/contracts";

export function selectEvidenceBuild(
  builds: readonly Build[],
  requestedBuildId: string | null,
  activeServedBuildId: string | null,
): Build | undefined {
  const inspectable = builds.filter((build) => build.canonical_snapshot_id);
  return (
    inspectable.find((build) => build.id === requestedBuildId) ??
    inspectable.find((build) => build.id === activeServedBuildId) ??
    inspectable[0]
  );
}
