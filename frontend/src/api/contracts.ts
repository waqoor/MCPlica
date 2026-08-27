import type { components } from "./generated/schema";

type Schema<Name extends keyof components["schemas"]> =
  components["schemas"][Name];

export type UUID = string;

// Transport DTOs are aliases of the tracked FastAPI OpenAPI artifact. Keep
// presentation-only enrichment explicit below instead of adding phantom wire
// fields to these authoritative schemas.
export type UserRole = Schema<"UserRole">;
export type RuntimeEffectState = Schema<"RuntimeEffectState">;
export type User = Schema<"UserRead">;
export type Project = Schema<"ProjectRead">;
export type CleanupJob = Schema<"CleanupJobRead">;

export type SourceKind = Schema<"SourceKind">;
export type SourceOrigin = Schema<"SourceOrigin">;
export type SourceIssue = Schema<"SourceIssueRead">;
export type SourceVersionWire = Schema<"SourceVersionRead">;
export type SourceVersionSummary = Schema<"SourceVersionSummaryRead">;
export type SourceVersionMetadata = Schema<"SourceVersionMetadataRead">;
export type SourceVersion = SourceVersionWire & Partial<SourceVersionMetadata>;
export type ProjectSource = Omit<
  Schema<"SourceSummaryRead">,
  "latest_version"
> & {
  readonly latest_version:
    (SourceVersionSummary & Partial<SourceVersionMetadata>) | null;
};

export type ServerCandidate = Schema<"ServerCandidateRead">;
export type OperationServerRouting = Schema<"OperationServerRoutingRead">;
export type SecuritySchemeDiscovery = Schema<"SecuritySchemeDiscoveryRead">;
export type OperationSecurityRequirement =
  Schema<"OperationSecurityRequirementRead">;
export type SourceConfigurationDiscovery =
  Schema<"SourceConfigurationDiscoveryRead">;

export type BuildStatus = Schema<"BuildStatus">;
export type BuildTrigger = Schema<"BuildTrigger">;
export type Build = Schema<"BuildRead">;
export type BuildPage = Schema<"BuildPageRead">;
export type BuildAIRun = Schema<"BuildAIRunRead">;
export type BuildAdmissionEntry = Schema<"QueuedBuildAdmissionRead">;
export type BuildAdmissionOverview = Schema<"BuildAdmissionOverviewRead">;
export type BuildMetrics = Schema<"BuildMetricsRead">;
export type MCPManifest = Schema<"MCPManifest">;
export type ValidationFinding = Schema<"ValidationFindingRead">;
export type ValidationReport = Schema<"ValidationReportRead">;
export type Operation = Schema<"OperationPageItemRead">;
export type OperationPage = Schema<"OperationPageRead">;
export type BuildDiff = Schema<"BuildDiffRead">;
export type OperationExclusion = Schema<"OperationExclusionRead">;

export type DeploymentStatus = Schema<"DeploymentStatus">;
export type DeploymentActivationPhase = Schema<"DeploymentActivationPhase">;
export type Deployment = Schema<"DeploymentRead">;
export type DeploymentPage = Schema<"DeploymentPageRead">;

export type Credential = Schema<"CredentialRead">;

export type McpAuthMode = Schema<"MCPAuthMode">;
export type McpAuthConfigUpdateWire = Schema<"MCPAuthConfigUpdate">;
export type McpAccessTokenWire = Schema<"MCPAccessTokenRead">;
export type McpAccessToken = McpAccessTokenWire & {
  readonly token?: string;
};

type McpOidcOptionalFields = Pick<
  McpAuthConfigUpdateWire,
  "required_scopes" | "jwks_url" | "allowed_algorithms"
>;

// The backend validator is mode-discriminated. Preserve that invariant in the
// command type so non-OIDC modes cannot accidentally retain hidden verifier
// fields and OIDC cannot be submitted without its required identity fields.
export type McpAuthModePayload =
  | { readonly mode: "static_bearer" | "disabled_dev" }
  | (McpOidcOptionalFields & {
      readonly mode: "external_oauth_oidc";
      readonly issuer_url: string;
      readonly audiences: readonly string[];
    });

// The UI intentionally normalizes the admin and builder-safe access endpoints
// into one presentation model. Its wire inputs remain generated and validated.
export type McpAccessConfig = {
  readonly project_id: UUID;
  readonly mode: McpAuthMode;
  readonly issuer_url: string | null;
  readonly jwks_url: string | null;
  readonly audiences: readonly string[];
  readonly required_scopes: readonly string[];
  readonly allowed_algorithms: readonly string[];
  readonly updated_at: string | null;
  readonly development_mode?: boolean;
  readonly configured: boolean;
  readonly tokens?: readonly McpAccessToken[];
  readonly runtime_effect_state: RuntimeEffectState;
  readonly runtime_command_id: UUID | null;
  readonly runtime_error_code: string | null;
  readonly remediation?: string | null;
};

export type JourneyStepState = Schema<"JourneyStepState">;
export type JourneyStep = Schema<"JourneyStepRecord">;
export type JourneySource = Schema<"JourneySourceRecord">;
export type ProjectJourney = Schema<"ProjectJourneyRead">;

export type AuditEvent = Schema<"AuditEventRead">;

// Readiness is a frontend presentation model composed from the health endpoint.
export type ReadinessCheck = {
  readonly name: string;
  readonly status: "ready" | "degraded" | "unavailable" | "unknown";
  readonly detail?: string | null;
};
export type Readiness = {
  readonly status: "ready" | "degraded" | "unavailable";
  readonly checks: readonly ReadinessCheck[];
};

export type SystemSettings = Schema<"SystemSettingsRead">;
export type ModelSettings = Schema<"ModelSettingsRead">;
export type ModelCatalogItem = Schema<"ModelCatalogItem">;

export type Page<T> = {
  readonly items: readonly T[];
  readonly total: number;
  readonly page: number;
  readonly page_size: number;
};
