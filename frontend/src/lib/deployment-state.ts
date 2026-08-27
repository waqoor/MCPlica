export function resolveDeploymentState<T extends { id: string }>(
  activeDeploymentId: string | null | undefined,
  history: readonly T[] | undefined,
  loadedActive?: T,
): { active: T | undefined; newestCandidate: T | null } {
  const active = activeDeploymentId
    ? loadedActive?.id === activeDeploymentId
      ? loadedActive
      : history?.find((deployment) => deployment.id === activeDeploymentId)
    : undefined;
  return {
    active,
    newestCandidate:
      history?.find((deployment) => deployment.id !== activeDeploymentId) ??
      null,
  };
}

export function hasRollbackCapability(deployment: {
  rollback_eligible: boolean;
}): boolean {
  return deployment.rollback_eligible;
}
