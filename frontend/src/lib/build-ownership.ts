import type { Build } from "@/api/contracts";
import { ApiError } from "@/api/client";

export function buildOwnershipError(
  build: Pick<Build, "id" | "project_id">,
  requestedProjectId: string | undefined,
): ApiError | null {
  if (requestedProjectId && build.project_id === requestedProjectId)
    return null;
  return new ApiError(
    404,
    "This build does not belong to the project in the current route.",
    "BUILD_PROJECT_MISMATCH",
    {
      build_id: build.id,
      requested_project_id: requestedProjectId ?? null,
      actual_project_id: build.project_id,
    },
  );
}

export function projectBuildNotFoundError(
  buildId: string,
  requestedProjectId: string,
): ApiError {
  return new ApiError(
    404,
    "The requested build was not found in the project in the current route.",
    "BUILD_NOT_FOUND_IN_PROJECT",
    {
      build_id: buildId,
      requested_project_id: requestedProjectId,
    },
  );
}
