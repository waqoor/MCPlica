import type {
  Build,
  BuildStatus,
  DeploymentStatus,
  User,
} from "@/api/contracts";

const ACTIVE_BUILD_STATUSES: BuildStatus[] = [
  "QUEUED",
  "INGESTING",
  "PARSING",
  "INDEXING",
  "ANALYZING",
  "COMPILING",
  "VALIDATING",
  "PACKAGING",
];

export function buildIsActive(status: BuildStatus): boolean {
  return ACTIVE_BUILD_STATUSES.includes(status);
}

export function buildCanCancel(status: BuildStatus): boolean {
  return ACTIVE_BUILD_STATUSES.includes(status);
}

export function buildCanDeploy(
  build: Build | null | undefined,
  accessConfigured: boolean,
): boolean {
  return build?.status === "READY" && accessConfigured;
}

export function deploymentIsActive(status: DeploymentStatus): boolean {
  return [
    "PENDING",
    "DEPLOYING",
    "HEALTHCHECK",
    "RUNNING",
    "UNHEALTHY",
  ].includes(status);
}

export function isAdmin(user: User | null | undefined): boolean {
  return user?.role === "admin";
}

export function canDeploy(
  user: User | null | undefined,
  buildersCanDeploy: boolean,
): boolean {
  return isAdmin(user) || (user?.role === "builder" && buildersCanDeploy);
}
