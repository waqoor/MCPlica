import type { Operation, OperationExclusion } from "@/api/contracts";

export type OperationPolicyState = {
  readonly excludedInBuild: boolean;
  readonly currentlyExcluded: boolean;
  readonly changedSinceBuild: boolean;
};

export function operationPolicyState(
  operation: Operation,
  currentExclusion?: OperationExclusion,
): OperationPolicyState {
  const currentlyExcluded =
    currentExclusion !== undefined || operation.current_exclusion_id !== null;
  return {
    excludedInBuild: operation.excluded_in_build,
    currentlyExcluded,
    changedSinceBuild: operation.excluded_in_build !== currentlyExcluded,
  };
}
