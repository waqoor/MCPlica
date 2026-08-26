export type UUID = string;

export type UserRole = "admin" | "builder";

export type User = {
  id: UUID;
  email: string;
  display_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
  last_login_at: string | null;
};

export type Project = {
  id: UUID;
  name: string;
  slug: string;
  description: string | null;
  is_enabled: boolean;
  default_base_url: string | null;
  mcp_hostname: string;
  created_by: UUID;
  active_build_id?: UUID | null;
  active_deployment_id?: UUID | null;
  created_at: string;
  updated_at: string;
};

export type SourceKind = "openapi" | "api_inventory" | "documentation";
export type SourceOrigin = "upload" | "url";

export type SourceVersion = {
  id: UUID;
  source_id: UUID;
  content_sha256: string;
  media_type: string;
  byte_size: number;
  detected_format: string;
  source_etag: string | null;
  source_last_modified: string | null;
  created_by: UUID;
  created_at: string;
  deduplicated: boolean;
  parse_status?: "pending" | "valid" | "invalid";
  spec_version?: string | null;
  operation_count?: number | null;
  servers?: string[];
  auth_schemes?: string[];
  errors?: SourceIssue[];
  preview_markdown?: string | null;
  indexed_chunk_count?: number | null;
  embedding_model?: string | null;
  embedding_dimensions?: number | null;
  index_status?: string | null;
};

export type SourceIssue = {
  code: string;
  message: string;
  location?: string | null;
  severity: "error" | "warning" | "info";
};

export type ProjectSource = {
  id: UUID;
  project_id: UUID;
  kind: SourceKind;
  name: string;
  origin_type: SourceOrigin;
  source_url: string | null;
  is_primary: boolean;
  created_at: string;
  latest_version?: SourceVersion | null;
  version_count?: number;
};

export const BUILD_STATUSES = [
  "QUEUED",
  "INGESTING",
  "PARSING",
  "INDEXING",
  "ANALYZING",
  "COMPILING",
  "VALIDATING",
  "PACKAGING",
  "READY",
  "FAILED",
  "CANCELLED",
] as const;

export type BuildStatus = (typeof BUILD_STATUSES)[number];
export type BuildTrigger =
  "initial" | "source_change" | "manual_review" | "manual_rebuild";

export type Build = {
  id: UUID;
  project_id: UUID;
  project_name?: string;
  sequence: number;
  status: BuildStatus;
  trigger: BuildTrigger;
  previous_build_id: UUID | null;
  compiler_version: string | null;
  manifest_schema_version: string | null;
  runtime_compatibility: string | null;
  analysis_model: string | null;
  validation_model: string | null;
  embedding_model: string | null;
  embedding_dimensions: number | null;
  prompt_bundle_version: string | null;
  manifest_sha256: string | null;
  artifact_sha256: string | null;
  error_code: string | null;
  error_summary: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  stage_counts?: Record<string, number>;
  warning_count?: number;
};

export type ValidationFinding = {
  code: string;
  severity: "error" | "warning" | "info";
  stage: string;
  operation_key: string | null;
  source_ref?: { source_version_id?: UUID; path?: string } | null;
  message: string;
  details?: Record<string, unknown>;
};

export type ValidationReport = {
  id: UUID;
  build_id: UUID;
  overall_status: "pass" | "fail";
  operation_source_count: number;
  operation_excluded_count: number;
  operation_expected_count: number;
  operation_generated_count: number;
  coverage_percent: number;
  blocking_error_count: number;
  warning_count: number;
  findings: ValidationFinding[];
  created_at: string;
};

export type Operation = {
  key: string;
  source_operation_id: string | null;
  method: string;
  path_template: string;
  tool_name: string | null;
  title: string | null;
  source_summary: string | null;
  source_description: string | null;
  enriched_description: string | null;
  input_schema: Record<string, unknown> | null;
  auth_mapping: string[];
  provenance: Array<{ source_version_id?: UUID; path?: string; kind?: string }>;
  semantic_warnings: string[];
  confidence: number | null;
  excluded: boolean;
  exclusion_id?: UUID | null;
  exclusion_reason: string | null;
};

export type BuildDiff = {
  added_operations: string[];
  removed_operations: string[];
  changed_operations: Array<{ operation_key: string; changes: string[] }>;
  unchanged_operations: string[];
  changed_schemas: string[];
  changed_security: string[];
  changed_documents: UUID[];
};

export const DEPLOYMENT_STATUSES = [
  "PENDING",
  "DEPLOYING",
  "HEALTHCHECK",
  "RUNNING",
  "UNHEALTHY",
  "STOPPING",
  "STOPPED",
  "FAILED",
] as const;

export type DeploymentStatus = (typeof DEPLOYMENT_STATUSES)[number];

export type Deployment = {
  id: UUID;
  project_id: UUID;
  project_name?: string;
  build_id: UUID;
  build_sequence?: number;
  status: DeploymentStatus;
  hostname: string;
  endpoint_url?: string;
  image_ref: string;
  image_digest: string | null;
  manifest_sha256: string;
  health_status: string | null;
  error_code: string | null;
  error_summary: string | null;
  created_at: string;
  started_at: string | null;
  stopped_at: string | null;
  failed_at: string | null;
};

export type Credential = {
  id: UUID;
  project_id: UUID;
  name: string;
  scheme_type: string;
  metadata: Record<string, string | number | boolean | null>;
  configured: boolean;
  created_by: UUID;
  created_at: string;
  rotated_at: string | null;
  revoked_at: string | null;
};

export type McpAuthMode =
  "static_bearer" | "external_oauth_oidc" | "disabled_dev";

export type McpAccessConfig = {
  project_id: UUID;
  mode: McpAuthMode;
  issuer_url: string | null;
  audiences: string[];
  required_scopes: string[];
  updated_at: string | null;
  development_mode?: boolean;
  configured: boolean;
  tokens?: McpAccessToken[];
};

export type McpAccessToken = {
  id: UUID;
  project_id: UUID;
  name: string;
  token_prefix: string;
  token?: string;
  created_at: string;
  expires_at: string | null;
  last_used_at: string | null;
  revoked_at: string | null;
};

export type DocumentIndexGeneration = {
  id: UUID;
  project_id: UUID;
  build_id: UUID | null;
  embedding_model: string;
  dimensions: number;
  generation_key: string;
  chunk_count: number;
  status: string;
  created_at: string;
};

export type AuditEvent = {
  id: UUID;
  actor_user_id: UUID | null;
  actor_display_name?: string | null;
  event_type: string;
  entity_type: string;
  entity_id: UUID | null;
  project_id: UUID | null;
  project_name?: string | null;
  request_id: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type ReadinessCheck = {
  name: string;
  status: "ready" | "degraded" | "unavailable" | "unknown";
  detail?: string | null;
};

export type Readiness = {
  status: "ready" | "degraded" | "unavailable";
  checks: ReadinessCheck[];
};

export type SystemSettings = {
  builders_can_deploy: boolean;
  mcp_base_domain: string;
  build_concurrency: number;
  source_retention_days: number | null;
  build_retention_count: number | null;
  max_upload_bytes: number;
  max_operations_per_project: number;
  max_document_chunks_per_project: number;
  environment: "development" | "production" | "test";
};

export type ModelSettings = {
  openrouter_configured: boolean;
  analysis_model: string | null;
  validation_model: string | null;
  embedding_model: string | null;
  embedding_dimensions: number | null;
  include_documentation_in_analysis: boolean;
  updated_at: string | null;
};

export type ModelCatalogItem = {
  id: string;
  name: string;
  context_length?: number;
  supports_structured_outputs: boolean;
  supports_embeddings: boolean;
};

export type Page<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};
