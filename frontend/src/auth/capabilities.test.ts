import { describe, expect, it } from "vitest";
import { capabilitiesFor } from "./capabilities";

describe("capabilitiesFor", () => {
  it("grants installation, secret, audit, and lifecycle controls to admins", () => {
    expect(capabilitiesFor("admin", false)).toEqual({
      canViewAudit: true,
      canManageCredentials: true,
      canManageMcpAccess: true,
      canDeleteProject: true,
      canManageInstallation: true,
      canManageModels: true,
      canManageUsers: true,
      canDeploy: true,
      canChangeProjectLifecycle: true,
    });
  });

  it("keeps Builder secret and administration capabilities denied", () => {
    const capabilities = capabilitiesFor("builder", true);

    expect(capabilities.canDeploy).toBe(true);
    expect(capabilities.canChangeProjectLifecycle).toBe(true);
    expect(capabilities.canViewAudit).toBe(false);
    expect(capabilities.canManageCredentials).toBe(false);
    expect(capabilities.canManageMcpAccess).toBe(false);
    expect(capabilities.canDeleteProject).toBe(false);
    expect(capabilities.canManageInstallation).toBe(false);
    expect(capabilities.canManageModels).toBe(false);
    expect(capabilities.canManageUsers).toBe(false);
  });

  it("fails Builder deployment capabilities closed when the setting is off", () => {
    const capabilities = capabilitiesFor("builder", false);

    expect(capabilities.canDeploy).toBe(false);
    expect(capabilities.canChangeProjectLifecycle).toBe(false);
  });

  it("grants no capabilities without an authenticated role", () => {
    expect(Object.values(capabilitiesFor(null, true))).not.toContain(true);
  });
});
