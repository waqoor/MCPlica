import { useQuery } from "@tanstack/react-query";
import { settingsApi } from "@/api/settings";
import type { UserRole } from "@/api/contracts";
import { useAuth } from "./use-auth";

export type Capabilities = {
  canViewAudit: boolean;
  canManageCredentials: boolean;
  canManageMcpAccess: boolean;
  canDeleteProject: boolean;
  canManageInstallation: boolean;
  canManageModels: boolean;
  canManageUsers: boolean;
  canDeploy: boolean;
  canChangeProjectLifecycle: boolean;
};

export function capabilitiesFor(
  role: UserRole | null | undefined,
  buildersCanDeploy: boolean,
): Capabilities {
  const admin = role === "admin";
  const deployer = admin || (role === "builder" && buildersCanDeploy);
  return {
    canViewAudit: admin,
    canManageCredentials: admin,
    canManageMcpAccess: admin,
    canDeleteProject: admin,
    canManageInstallation: admin,
    canManageModels: admin,
    canManageUsers: admin,
    canDeploy: deployer,
    canChangeProjectLifecycle: deployer,
  };
}

export function useCapabilities(): Capabilities & { isLoading: boolean } {
  const { user } = useAuth();
  const settings = useQuery({
    queryKey: ["settings"],
    queryFn: ({ signal }) => settingsApi.get(signal),
    staleTime: 60_000,
  });
  return {
    ...capabilitiesFor(user?.role, settings.data?.builders_can_deploy ?? false),
    isLoading: settings.isPending,
  };
}
