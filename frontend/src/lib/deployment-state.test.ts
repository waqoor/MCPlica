import { describe, expect, it } from "vitest";
import {
  hasRollbackCapability,
  resolveDeploymentState,
} from "./deployment-state";

describe("resolveDeploymentState", () => {
  it("keeps the authoritative older active runtime when the newest candidate fails", () => {
    const failedCandidate = { id: "candidate", status: "failed" };
    const healthyActive = { id: "active", status: "running" };

    const result = resolveDeploymentState(
      healthyActive.id,
      [failedCandidate, healthyActive],
      healthyActive,
    );

    expect(result.active).toBe(healthyActive);
    expect(result.newestCandidate).toBe(failedCandidate);
  });

  it("never promotes the newest row when the active id is absent", () => {
    const failedCandidate = { id: "candidate", status: "failed" };

    const result = resolveDeploymentState("active-not-in-page", [
      failedCandidate,
    ]);

    expect(result.active).toBeUndefined();
    expect(result.newestCandidate).toBe(failedCandidate);
  });

  it("renders rollback only from the authoritative API capability", () => {
    expect(hasRollbackCapability({ rollback_eligible: true })).toBe(true);
    expect(hasRollbackCapability({ rollback_eligible: false })).toBe(false);
  });
});
