// Runtime validators are generated against the Zod 3 compatibility surface.
// The application uses Zod 4, whose package deliberately ships this stable
// compatibility entrypoint for generators that emit Zod 3 syntax.
import { z } from "zod/v3";

const actor: z.ZodTypeAny = z.union([z.string(), z.null()]).optional();
const AuditEventRead: z.ZodTypeAny = z
  .object({
    actor_user_id: z.union([z.string(), z.null()]),
    created_at: z.string().datetime({ offset: true }),
    entity_id: z.union([z.string(), z.null()]),
    entity_type: z.string(),
    event_type: z.string(),
    id: z.string().uuid(),
    metadata: z.object({}).partial().strict().passthrough(),
    project_id: z.union([z.string(), z.null()]),
    request_id: z.union([z.string(), z.null()]),
  })
  .strict();
const AuditPage: z.ZodTypeAny = z
  .object({
    items: z.array(AuditEventRead),
    page: z.number().int(),
    page_size: z.number().int(),
    total: z.number().int(),
  })
  .strict();
const ValidationError: z.ZodTypeAny = z
  .object({
    ctx: z.object({}).partial().strict().passthrough().optional(),
    input: z.unknown().optional(),
    loc: z.array(z.union([z.string(), z.number()])),
    msg: z.string(),
    type: z.string(),
  })
  .strict()
  .passthrough();
const HTTPValidationError: z.ZodTypeAny = z
  .object({ detail: z.array(ValidationError) })
  .partial()
  .strict()
  .passthrough();
const LoginRequest: z.ZodTypeAny = z
  .object({ email: z.string().email(), password: z.string().min(1).max(1024) })
  .strict();
const UserRole: z.ZodTypeAny = z.enum(["admin", "builder"]);
const UserRead: z.ZodTypeAny = z
  .object({
    created_at: z.union([z.string(), z.null()]).optional(),
    display_name: z.string(),
    email: z.string().email(),
    id: z.string().uuid(),
    is_active: z.boolean(),
    last_login_at: z.union([z.string(), z.null()]).optional(),
    role: UserRole,
    updated_at: z.union([z.string(), z.null()]).optional(),
  })
  .strict();
const AuthResponse: z.ZodTypeAny = z
  .object({
    access_expires_at: z.string().datetime({ offset: true }),
    user: UserRead,
  })
  .strict();
const BuildAdmissionState: z.ZodTypeAny = z.enum([
  "waiting",
  "admitted",
  "running",
]);
const BuildStatus: z.ZodTypeAny = z.enum([
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
]);
const QueuedBuildAdmissionRead: z.ZodTypeAny = z
  .object({
    admitted_at: z.union([z.string(), z.null()]),
    build_id: z.string().uuid(),
    lease_expires_at: z.union([z.string(), z.null()]),
    position: z.union([z.number(), z.null()]),
    project_id: z.string().uuid(),
    state: BuildAdmissionState,
    status: BuildStatus,
  })
  .strict();
const BuildAdmissionOverviewRead: z.ZodTypeAny = z
  .object({
    configured_concurrency: z.number().int(),
    effective_concurrency: z.number().int(),
    entries: z.array(QueuedBuildAdmissionRead),
    waiting_count: z.number().int(),
  })
  .strict();
const status: z.ZodTypeAny = z.union([BuildStatus, z.null()]).optional();
const BuildTrigger: z.ZodTypeAny = z.enum([
  "initial",
  "source_change",
  "manual_review",
  "manual_rebuild",
]);
const BuildRead: z.ZodTypeAny = z
  .object({
    admission_acquired_at: z.union([z.string(), z.null()]),
    admission_attempt_count: z.number().int(),
    admission_enqueued_at: z.union([z.string(), z.null()]),
    admission_heartbeat_at: z.union([z.string(), z.null()]),
    admission_lease_expires_at: z.union([z.string(), z.null()]),
    admission_released_at: z.union([z.string(), z.null()]),
    analysis_model: z.union([z.string(), z.null()]),
    artifact_sha256: z.union([z.string(), z.null()]),
    cancellation_acknowledged_at: z.union([z.string(), z.null()]),
    cancellation_requested_at: z.union([z.string(), z.null()]),
    cancellation_requested_by: z.union([z.string(), z.null()]),
    canonical_snapshot_id: z.union([z.string(), z.null()]),
    compiler_version: z.string(),
    completed_at: z.union([z.string(), z.null()]),
    created_at: z.string().datetime({ offset: true }),
    embedding_dimensions: z.union([z.number(), z.null()]),
    embedding_model: z.union([z.string(), z.null()]),
    error_code: z.union([z.string(), z.null()]),
    error_summary: z.union([z.string(), z.null()]),
    executable_configuration_sha256: z.union([z.string(), z.null()]),
    id: z.string().uuid(),
    manifest_schema_version: z.string(),
    manifest_sha256: z.union([z.string(), z.null()]),
    pipeline_stage: z.union([BuildStatus, z.null()]),
    previous_build_id: z.union([z.string(), z.null()]),
    project_id: z.string().uuid(),
    prompt_bundle_version: z.union([z.string(), z.null()]),
    runtime_compatibility: z.string(),
    sequence: z.number().int(),
    started_at: z.union([z.string(), z.null()]),
    status: BuildStatus,
    trigger: BuildTrigger,
    validation_model: z.union([z.string(), z.null()]),
  })
  .strict();
const BuildPageRead: z.ZodTypeAny = z
  .object({
    has_active: z.boolean(),
    items: z.array(BuildRead),
    page: z.number().int().gte(1),
    page_size: z.number().int().gte(1).lte(200),
    total: z.number().int().gte(0),
  })
  .strict();
const BuildMetricsRead: z.ZodTypeAny = z
  .object({
    active: z.number().int().gte(0),
    failed: z.number().int().gte(0),
    total: z.number().int().gte(0),
  })
  .strict();
const BuildAIRunRead: z.ZodTypeAny = z
  .object({
    build_id: z.string().uuid(),
    cost: z.union([z.object({}).partial().strict().passthrough(), z.null()]),
    created_at: z.string().datetime({ offset: true }),
    error_code: z.union([z.string(), z.null()]),
    id: z.string().uuid(),
    input_context_sha256: z.string(),
    latency_ms: z.union([z.number(), z.null()]),
    model: z.string(),
    operation_key: z.union([z.string(), z.null()]),
    prompt_template_id: z.string(),
    prompt_template_version: z.string(),
    provider: z.string(),
    response_schema_id: z.string(),
    response_sha256: z.union([z.string(), z.null()]),
    retrieved_chunk_ids: z.array(z.string()),
    run_key: z.string(),
    stage: z.string(),
    status: z.string(),
    usage: z.union([z.object({}).partial().strict().passthrough(), z.null()]),
  })
  .strict();
const OperationChangeRead: z.ZodTypeAny = z
  .object({ changes: z.array(z.string()), operation_key: z.string() })
  .strict();
const BuildDiffRead: z.ZodTypeAny = z
  .object({
    added_operations: z.array(z.string()),
    changed_documents: z.array(z.string().uuid()),
    changed_operations: z.array(OperationChangeRead),
    changed_schemas: z.array(z.string()),
    changed_security: z.array(z.string()),
    removed_operations: z.array(z.string()),
    unchanged_operations: z.array(z.string()),
  })
  .strict();
const AuthProfile: z.ZodTypeAny = z
  .object({
    credential_ref: z.union([z.string(), z.null()]).optional(),
    id: z.string(),
    location: z.union([z.enum(["header", "query"]), z.null()]).optional(),
    name: z.union([z.string(), z.null()]).optional(),
    prefix: z.union([z.string(), z.null()]).optional(),
    scopes: z.array(z.string()).optional(),
    token_auth_method: z
      .enum(["client_secret_basic", "client_secret_post"])
      .optional()
      .default("client_secret_basic"),
    token_url: z.union([z.string(), z.null()]).optional(),
    type: z.enum([
      "none",
      "bearer",
      "api_key",
      "basic",
      "oauth2_client_credentials",
      "static_header",
    ]),
  })
  .strict();
const BuildMetadata: z.ZodTypeAny = z
  .object({
    analysis_model: z.union([z.string(), z.null()]).optional(),
    build_id: z.string(),
    canonical_sha256: z.string().regex(/^[a-f0-9]{64}$/),
    compiler_version: z.string(),
    created_at: z.string(),
    embedding_model: z.union([z.string(), z.null()]).optional(),
    prompt_bundle_version: z.union([z.string(), z.null()]).optional(),
    source_digest: z.string().regex(/^[a-f0-9]{64}$/),
    source_version_ids: z.array(z.string()).min(1),
    validation_model: z.union([z.string(), z.null()]).optional(),
  })
  .strict();
const ManifestProject: z.ZodTypeAny = z
  .object({ id: z.string(), name: z.string(), slug: z.string() })
  .strict();
const JsonScalar: z.ZodTypeAny = z.union([
  z.string(),
  z.number(),
  z.number(),
  z.boolean(),
  z.null(),
]);
const JsonValue: z.ZodTypeAny = z.lazy(() =>
  z.union([JsonScalar, z.array(JsonValue), z.record(JsonValue)]),
);
const MCPResource: z.ZodTypeAny = z
  .object({
    content: z.string(),
    description: z.union([z.string(), z.null()]).optional(),
    mime_type: z.string().optional().default("text/markdown"),
    name: z.string(),
    provenance: z.record(JsonValue).optional(),
    uri: z.string(),
  })
  .strict();
const RuntimeSecurity: z.ZodTypeAny = z
  .object({
    allow_insecure_none_only_in_development: z
      .boolean()
      .optional()
      .default(true),
    allowed_upstream_hosts: z.array(z.string()).min(1),
    default_max_response_bytes: z
      .number()
      .int()
      .gte(1024)
      .lte(50000000)
      .optional()
      .default(2000000),
    default_timeout_ms: z
      .number()
      .int()
      .gte(100)
      .lte(300000)
      .optional()
      .default(30000),
    inbound_auth_boundary: z.string().optional().default("deployment_overlay"),
    inbound_auth_mode: z
      .union([z.enum(["static_bearer", "oidc", "none"]), z.null()])
      .optional(),
  })
  .strict();
const ServerDefinition: z.ZodTypeAny = z
  .object({
    description: z.union([z.string(), z.null()]).optional(),
    id: z.string(),
    url: z.string().min(1).url(),
  })
  .strict();
const JsonObject: z.ZodTypeAny = z.record(JsonValue);
const MultipartFileMapping: z.ZodTypeAny = z
  .object({
    content_field: z.string(),
    content_type_field: z.union([z.string(), z.null()]).optional(),
    default_content_type: z
      .string()
      .optional()
      .default("application/octet-stream"),
    default_filename: z.string().optional().default("upload.bin"),
    filename_field: z.union([z.string(), z.null()]).optional(),
    part_name: z.string(),
    required: z.boolean().optional().default(false),
  })
  .strict();
const RequestBodyMapping: z.ZodTypeAny = z
  .object({
    media_type: z
      .enum([
        "application/json",
        "application/x-www-form-urlencoded",
        "multipart/form-data",
      ])
      .default("application/json"),
    multipart_files: z.array(MultipartFileMapping),
    required: z.boolean().default(false),
    tool_field: z.string().default("body"),
  })
  .partial()
  .strict();
const HttpMethod: z.ZodTypeAny = z.enum([
  "GET",
  "POST",
  "PUT",
  "PATCH",
  "DELETE",
  "HEAD",
  "OPTIONS",
  "TRACE",
]);
const ParameterTarget: z.ZodTypeAny = z.enum(["path", "query", "header"]);
const ParameterMapping: z.ZodTypeAny = z
  .object({
    allow_reserved: z.boolean().optional().default(false),
    explode: z.union([z.boolean(), z.null()]).optional(),
    required: z.boolean().optional().default(false),
    source_name: z.string(),
    style: z.union([z.string(), z.null()]).optional(),
    target: ParameterTarget,
    tool_field: z.string(),
  })
  .strict();
const RequestMapping: z.ZodTypeAny = z
  .object({
    body: z.union([RequestBodyMapping, z.null()]).optional(),
    method: HttpMethod,
    parameters: z.array(ParameterMapping).optional(),
    path: z.string().regex(/^\//),
    server_ref: z.string(),
  })
  .strict();
const ResponseDefinition: z.ZodTypeAny = z
  .object({
    description: z.union([z.string(), z.null()]).optional(),
    media_type: z.union([z.string(), z.null()]).optional(),
    schema: z.union([JsonObject, z.null()]).optional(),
    status_code: z.string(),
  })
  .strict();
const MCPTool: z.ZodTypeAny = z
  .object({
    description: z.string(),
    enabled: z.boolean().optional().default(true),
    input_schema: JsonObject,
    max_request_bytes: z
      .number()
      .int()
      .gte(1024)
      .lte(100000000)
      .optional()
      .default(10000000),
    max_response_bytes: z
      .number()
      .int()
      .gte(1024)
      .lte(50000000)
      .optional()
      .default(2000000),
    name: z.string().regex(/^[a-z_][a-z0-9_]{0,127}$/),
    operation_key: z.string(),
    output_schema: z.union([JsonObject, z.null()]).optional(),
    provenance: z.record(JsonValue).optional(),
    request_mapping: RequestMapping,
    responses: z.array(ResponseDefinition).optional(),
    security_profile_ref: z.union([z.string(), z.null()]).optional(),
    timeout_ms: z.number().int().gte(100).lte(300000).optional().default(30000),
    title: z.string(),
  })
  .strict();
const MCPManifest: z.ZodTypeAny = z
  .object({
    auth_profiles: z.array(AuthProfile).optional(),
    build: BuildMetadata,
    manifest_id: z.string().regex(/^[a-f0-9]{64}$/),
    project: ManifestProject,
    resources: z.array(MCPResource).optional(),
    runtime_compatibility: z.string().optional().default(">=1.0,<2.0"),
    schema_version: z.string().optional().default("mcp-manifest/v1"),
    security: RuntimeSecurity,
    servers: z.array(ServerDefinition).min(1),
    tools: z.array(MCPTool),
  })
  .strict();
const method: z.ZodTypeAny = z
  .union([
    z.enum([
      "GET",
      "POST",
      "PUT",
      "PATCH",
      "DELETE",
      "HEAD",
      "OPTIONS",
      "TRACE",
    ]),
    z.null(),
  ])
  .optional();
const OperationPageItemRead: z.ZodTypeAny = z
  .object({
    auth_mapping: z.array(z.string()),
    build_exclusion_id: z.union([z.string(), z.null()]),
    build_exclusion_reason: z.union([z.string(), z.null()]),
    confidence: z.union([z.number(), z.null()]),
    current_exclusion_id: z.union([z.string(), z.null()]),
    current_exclusion_reason: z.union([z.string(), z.null()]),
    enriched_description: z.union([z.string(), z.null()]),
    excluded_in_build: z.boolean(),
    input_schema: z.union([JsonObject, z.null()]),
    key: z.string(),
    method: z.string(),
    path_template: z.string(),
    provenance: z.array(JsonObject),
    semantic_warnings: z.array(z.string()),
    source_description: z.union([z.string(), z.null()]),
    source_operation_id: z.union([z.string(), z.null()]),
    source_summary: z.union([z.string(), z.null()]),
    title: z.union([z.string(), z.null()]),
    tool_name: z.union([z.string(), z.null()]),
  })
  .strict();
const OperationPageRead: z.ZodTypeAny = z
  .object({
    items: z.array(OperationPageItemRead),
    page: z.number().int().gte(1),
    page_size: z.number().int().gte(1).lte(200),
    policy_change_count: z.number().int().gte(0),
    total: z.number().int().gte(0),
  })
  .strict();
const FindingSeverity: z.ZodTypeAny = z.enum(["error", "warning", "info"]);
const ValidationSourceRefRead: z.ZodTypeAny = z
  .object({ path: z.string(), source_version_id: z.string().uuid() })
  .strict();
const ValidationFindingRead: z.ZodTypeAny = z
  .object({
    code: z.string(),
    details: JsonObject.optional(),
    message: z.string(),
    operation_key: z.union([z.string(), z.null()]),
    severity: FindingSeverity,
    source_ref: z.union([ValidationSourceRefRead, z.null()]),
    stage: z.string(),
  })
  .strict();
const ValidationStatus: z.ZodTypeAny = z.enum(["pass", "fail"]);
const ValidationReportRead: z.ZodTypeAny = z
  .object({
    blocking_error_count: z.number().int(),
    build_id: z.string().uuid(),
    coverage_percent: z.number(),
    created_at: z.string().datetime({ offset: true }),
    findings: z.array(ValidationFindingRead),
    id: z.string().uuid(),
    operation_excluded_count: z.number().int(),
    operation_expected_count: z.number().int(),
    operation_generated_count: z.number().int(),
    operation_source_count: z.number().int(),
    overall_status: ValidationStatus,
    warning_count: z.number().int(),
  })
  .strict();
const CleanupJobKind: z.ZodTypeAny = z.enum([
  "project_delete",
  "source_delete",
  "retention",
  "orphan_guard",
]);
const CleanupJobStatus: z.ZodTypeAny = z.enum([
  "pending",
  "running",
  "retrying",
  "completed",
  "failed",
]);
const CleanupJobRead: z.ZodTypeAny = z
  .object({
    completed_at: z.union([z.string(), z.null()]),
    completed_targets: z.number().int(),
    created_at: z.string().datetime({ offset: true }),
    failed_targets: z.number().int(),
    id: z.string().uuid(),
    kind: CleanupJobKind,
    last_error_code: z.union([z.string(), z.null()]),
    last_error_summary: z.union([z.string(), z.null()]),
    project_id: z.union([z.string(), z.null()]),
    request_id: z.union([z.string(), z.null()]),
    requested_by: z.union([z.string(), z.null()]),
    skipped_targets: z.number().int(),
    status: CleanupJobStatus,
    total_targets: z.number().int(),
    updated_at: z.string().datetime({ offset: true }),
  })
  .strict();
const DeploymentActivationPhase: z.ZodTypeAny = z.enum([
  "verified",
  "retiring_previous",
  "running",
  "legacy_running",
  "failed",
]);
const DeploymentStatus: z.ZodTypeAny = z.enum([
  "pending",
  "deploying",
  "healthcheck",
  "running",
  "unhealthy",
  "stopping",
  "stopped",
  "failed",
]);
const DeploymentRead: z.ZodTypeAny = z
  .object({
    activated_at: z.union([z.string(), z.null()]),
    activation_phase: z.union([DeploymentActivationPhase, z.null()]),
    activation_proof_sha256: z.union([z.string(), z.null()]),
    activation_verified_at: z.union([z.string(), z.null()]),
    auth_overlay_sha256: z.union([z.string(), z.null()]),
    build_id: z.string().uuid(),
    container_id: z.union([z.string(), z.null()]),
    container_name: z.string(),
    created_at: z.string().datetime({ offset: true }),
    endpoint_url: z.string(),
    error_code: z.union([z.string(), z.null()]),
    error_summary: z.union([z.string(), z.null()]),
    failed_at: z.union([z.string(), z.null()]),
    health_status: z.union([z.string(), z.null()]),
    hostname: z.string(),
    id: z.string().uuid(),
    image_digest: z.union([z.string(), z.null()]),
    image_ref: z.string(),
    manifest_sha256: z.string(),
    network_name: z.string(),
    project_id: z.string().uuid(),
    rollback_eligible: z.boolean(),
    runtime_version: z.string(),
    started_at: z.union([z.string(), z.null()]),
    status: DeploymentStatus,
    stopped_at: z.union([z.string(), z.null()]),
  })
  .strict();
const HealthRead: z.ZodTypeAny = z
  .object({ service: z.string(), status: z.string() })
  .strict();
const RuntimeEffectState: z.ZodTypeAny = z.enum([
  "effective",
  "pending",
  "failed",
]);
const ProjectRead: z.ZodTypeAny = z
  .object({
    active_build_id: z.union([z.string(), z.null()]),
    active_deployment_id: z.union([z.string(), z.null()]),
    active_server_ref: z.union([z.string(), z.null()]),
    created_at: z.string().datetime({ offset: true }),
    created_by: z.string().uuid(),
    default_base_url: z.union([z.string(), z.null()]),
    description: z.union([z.string(), z.null()]),
    id: z.string().uuid(),
    is_enabled: z.boolean(),
    mcp_hostname: z.string(),
    name: z.string(),
    runtime_command_id: z.union([z.string(), z.null()]),
    runtime_effect_state: RuntimeEffectState,
    runtime_error_code: z.union([z.string(), z.null()]),
    server_mappings: z.record(z.string()),
    slug: z.string(),
    updated_at: z.string().datetime({ offset: true }),
  })
  .strict()
  .passthrough();
const ProjectCreate: z.ZodTypeAny = z
  .object({
    default_base_url: z.union([z.string(), z.null()]).optional(),
    description: z.union([z.string(), z.null()]).optional(),
    name: z.string().min(1).max(160),
    slug: z.string().min(3).max(63),
  })
  .strict();
const ProjectUpdate: z.ZodTypeAny = z
  .object({
    active_server_ref: z.union([z.string(), z.null()]),
    default_base_url: z.union([z.string(), z.null()]),
    description: z.union([z.string(), z.null()]),
    is_enabled: z.union([z.boolean(), z.null()]),
    name: z.union([z.string(), z.null()]),
    server_mappings: z.union([z.record(z.string()), z.null()]),
  })
  .partial()
  .strict();
const BuildCreate: z.ZodTypeAny = z
  .object({ trigger: z.string().default("initial") })
  .partial()
  .strict();
const CredentialScheme: z.ZodTypeAny = z.enum([
  "bearer",
  "api_key_header",
  "api_key_query",
  "basic",
  "oauth2_client_credentials",
  "static_headers",
]);
const CredentialRead: z.ZodTypeAny = z
  .object({
    configured: z.boolean().optional().default(true),
    created_at: z.string().datetime({ offset: true }),
    created_by: z.string().uuid(),
    id: z.string().uuid(),
    metadata: z.object({}).partial().strict().passthrough(),
    name: z.string(),
    project_id: z.string().uuid(),
    revoked_at: z.union([z.string(), z.null()]),
    rotated_at: z.union([z.string(), z.null()]),
    runtime_command_id: z.union([z.string(), z.null()]),
    runtime_effect_state: RuntimeEffectState,
    runtime_error_code: z.union([z.string(), z.null()]),
    scheme_type: CredentialScheme,
  })
  .strict();
const CredentialSecretInput: z.ZodTypeAny = z
  .object({
    client_id: z.union([z.string(), z.null()]),
    client_secret: z.union([z.string(), z.null()]),
    headers: z.union([z.record(z.string()), z.null()]),
    password: z.union([z.string(), z.null()]),
    token: z.union([z.string(), z.null()]),
    username: z.union([z.string(), z.null()]),
    value: z.union([z.string(), z.null()]),
  })
  .partial()
  .strict();
const CredentialCreate: z.ZodTypeAny = z
  .object({
    metadata: z.record(z.string()).optional(),
    name: z.string().min(1).max(160),
    scheme_type: CredentialScheme,
    secret: CredentialSecretInput,
  })
  .strict();
const CredentialRotate: z.ZodTypeAny = z
  .object({
    metadata: z.union([z.record(z.string()), z.null()]).optional(),
    secret: CredentialSecretInput,
  })
  .strict();
const DeploymentPageRead: z.ZodTypeAny = z
  .object({
    has_active: z.boolean(),
    items: z.array(DeploymentRead),
    page: z.number().int().gte(1),
    page_size: z.number().int().gte(1).lte(200),
    total: z.number().int().gte(0),
  })
  .strict();
const DeploymentCreate: z.ZodTypeAny = z
  .object({ build_id: z.string().uuid() })
  .strict();
const MCPAuthMode: z.ZodTypeAny = z.enum([
  "static_bearer",
  "external_oauth_oidc",
  "disabled_dev",
]);
const SourceKind: z.ZodTypeAny = z.enum([
  "openapi",
  "api_inventory",
  "documentation",
]);
const JourneySourceRecord: z.ZodTypeAny = z
  .object({
    id: z.string().uuid(),
    is_primary: z.boolean(),
    kind: SourceKind,
    name: z.string(),
    version_id: z.string().uuid(),
  })
  .strict();
const JourneyStepState: z.ZodTypeAny = z.enum([
  "complete",
  "current",
  "stale",
  "locked",
]);
const JourneyStepRecord: z.ZodTypeAny = z
  .object({
    authorized: z.boolean(),
    message: z.union([z.string(), z.null()]).optional(),
    number: z.number().int().gte(1).lte(10),
    reason_code: z.union([z.string(), z.null()]).optional(),
    remediation: z.union([z.string(), z.null()]).optional(),
    state: JourneyStepState,
  })
  .strict();
const ProjectJourneyRead: z.ZodTypeAny = z
  .object({
    access_configured: z.boolean(),
    access_mode: z.union([MCPAuthMode, z.null()]),
    access_remediation: z.union([z.string(), z.null()]),
    access_runtime_effect_state: RuntimeEffectState,
    active_build_id: z.union([z.string(), z.null()]),
    active_deployment_id: z.union([z.string(), z.null()]),
    active_deployment_status: z.union([DeploymentStatus, z.null()]),
    bound_security_schemes: z.array(z.string()),
    build_stale: z.boolean(),
    build_status: z.union([BuildStatus, z.null()]),
    can_deploy: z.boolean(),
    can_manage_credentials: z.boolean(),
    can_manage_mcp_access: z.boolean(),
    credential_mapping_complete: z.boolean(),
    credential_mapping_required: z.boolean(),
    deployability_reason_code: z.union([z.string(), z.null()]),
    deployability_remediation: z.union([z.string(), z.null()]),
    deployable: z.boolean(),
    deployment_transition_in_progress: z.boolean(),
    preflight_ready: z.boolean(),
    project_id: z.string().uuid(),
    requested_build_id: z.union([z.string(), z.null()]),
    resume_step: z.number().int().gte(1).lte(10),
    routing_complete: z.boolean(),
    selected_build_id: z.union([z.string(), z.null()]),
    source_version_ids: z.array(z.string().uuid()),
    sources: z.array(JourneySourceRecord),
    steps: z.array(JourneyStepRecord).min(10).max(10),
    validation_complete: z.boolean(),
    validation_status: z.union([ValidationStatus, z.null()]),
  })
  .strict();
const MCPAuthConfigRead: z.ZodTypeAny = z
  .object({
    audiences: z.array(z.string()),
    issuer_url: z.union([z.string(), z.null()]),
    metadata: z.object({}).partial().strict().passthrough(),
    mode: MCPAuthMode,
    project_id: z.string().uuid(),
    required_scopes: z.array(z.string()),
    runtime_command_id: z.union([z.string(), z.null()]),
    runtime_effect_state: RuntimeEffectState,
    runtime_error_code: z.union([z.string(), z.null()]),
    updated_at: z.string().datetime({ offset: true }),
    updated_by: z.string().uuid(),
  })
  .strict()
  .passthrough();
const MCPAccessTokenRead: z.ZodTypeAny = z
  .object({
    created_at: z.string().datetime({ offset: true }),
    created_by: z.string().uuid(),
    expires_at: z.union([z.string(), z.null()]),
    id: z.string().uuid(),
    last_used_at: z.union([z.string(), z.null()]),
    name: z.string(),
    project_id: z.string().uuid(),
    revoked_at: z.union([z.string(), z.null()]),
    runtime_command_id: z.union([z.string(), z.null()]),
    runtime_effect_state: RuntimeEffectState,
    runtime_error_code: z.union([z.string(), z.null()]),
    token_prefix: z.string(),
  })
  .strict()
  .passthrough();
const MCPAccessRead: z.ZodTypeAny = z
  .object({
    auth_config: z.union([MCPAuthConfigRead, z.null()]),
    tokens: z.array(MCPAccessTokenRead),
  })
  .strict();
const MCPAuthConfigUpdate: z.ZodTypeAny = z
  .object({
    allowed_algorithms: z.array(z.string()).max(20).optional(),
    audiences: z.array(z.string()).max(50).optional(),
    issuer_url: z.union([z.string(), z.null()]).optional(),
    jwks_url: z.union([z.string(), z.null()]).optional(),
    mode: MCPAuthMode,
    required_scopes: z.array(z.string()).max(100).optional(),
  })
  .strict();
const MCPAccessStatusRead: z.ZodTypeAny = z
  .object({
    configured: z.boolean(),
    mode: z.union([MCPAuthMode, z.null()]),
    project_id: z.string().uuid(),
    remediation: z.union([z.string(), z.null()]),
    runtime_command_id: z.union([z.string(), z.null()]),
    runtime_effect_state: RuntimeEffectState,
    runtime_error_code: z.union([z.string(), z.null()]),
  })
  .strict();
const MCPAccessTokenCreate: z.ZodTypeAny = z
  .object({
    expires_at: z.union([z.string(), z.null()]).optional(),
    name: z.string().min(1).max(160),
  })
  .strict();
const MCPAccessTokenIssued: z.ZodTypeAny = z
  .object({ plaintext: z.string(), token: MCPAccessTokenRead })
  .strict();
const MCPAccessTokenRotate: z.ZodTypeAny = z
  .object({ overlap_seconds: z.number().int().gte(0).lte(900).default(300) })
  .partial()
  .strict();
const OperationExclusionRead: z.ZodTypeAny = z
  .object({
    build_id: z.union([z.string(), z.null()]),
    created_at: z.string().datetime({ offset: true }),
    created_by: z.string().uuid(),
    id: z.string().uuid(),
    is_user_requested: z.boolean(),
    operation_key: z.string(),
    project_id: z.string().uuid(),
    reason: z.string(),
    reason_code: z.string(),
  })
  .strict();
const OperationExclusionCreate: z.ZodTypeAny = z
  .object({
    operation_key: z.string().min(1).max(160),
    reason: z.string().min(5).max(2000),
  })
  .strict();
const DeploymentRollback: z.ZodTypeAny = z
  .object({ target_deployment_id: z.string().uuid() })
  .strict();
const OperationServerRoutingRead: z.ZodTypeAny = z
  .object({
    candidate_refs: z.array(z.string()),
    configured_server_ref: z.union([z.string(), z.null()]),
    method: z.string(),
    operation_key: z.string(),
    path: z.string(),
    selected_server_ref: z.union([z.string(), z.null()]),
    selection_error: z.union([z.string(), z.null()]),
    selection_required: z.boolean(),
  })
  .strict();
const OperationSecurityRequirementRead: z.ZodTypeAny = z
  .object({
    alternatives: z.array(z.record(z.array(z.string()))),
    anonymous_allowed: z.boolean(),
    operation_key: z.string(),
  })
  .strict();
const SecuritySchemeDiscoveryRead: z.ZodTypeAny = z
  .object({
    advertised_scopes: z.array(z.string()),
    applicable_operation_keys: z.array(z.string()),
    location: z.union([z.string(), z.null()]),
    name: z.string(),
    optional_for_all_operations: z.boolean(),
    parameter_name: z.union([z.string(), z.null()]),
    source_pointer: z.string(),
    token_url: z.union([z.string(), z.null()]),
    type: z.string(),
  })
  .strict();
const ServerCandidateRead: z.ZodTypeAny = z
  .object({
    applicable_operation_keys: z.array(z.string()),
    description: z.union([z.string(), z.null()]),
    ref: z.string(),
    scope: z.enum([
      "root",
      "path",
      "operation",
      "project_default",
      "inventory",
    ]),
    source_pointer: z.string(),
    url: z.string(),
  })
  .strict();
const SourceConfigurationDiscoveryRead: z.ZodTypeAny = z
  .object({
    configuration_sha256: z.string(),
    operations: z.array(OperationServerRoutingRead),
    routing_complete: z.boolean(),
    security_requirements: z.array(OperationSecurityRequirementRead),
    security_schemes: z.array(SecuritySchemeDiscoveryRead),
    servers: z.array(ServerCandidateRead),
    source_version_ids: z.array(z.string().uuid()),
  })
  .strict();
const SourceVersionSummaryRead: z.ZodTypeAny = z
  .object({
    byte_size: z.number().int(),
    content_sha256: z.string(),
    created_at: z.string().datetime({ offset: true }),
    created_by: z.string().uuid(),
    deduplicated: z.boolean().optional().default(false),
    detected_format: z.string(),
    id: z.string().uuid(),
    index_generation_id: z.union([z.string(), z.null()]).optional(),
    indexed_chunk_count: z.union([z.number(), z.null()]).optional(),
    media_type: z.string(),
    metadata_build_id: z.union([z.string(), z.null()]).optional(),
    operation_count: z.union([z.number(), z.null()]).optional(),
    source_etag: z.union([z.string(), z.null()]),
    source_id: z.string().uuid(),
    source_last_modified: z.union([z.string(), z.null()]),
  })
  .strict();
const SourceOrigin: z.ZodTypeAny = z.enum(["upload", "url"]);
const SourceSummaryRead: z.ZodTypeAny = z
  .object({
    created_at: z.string().datetime({ offset: true }),
    health: z.enum(["missing", "pending", "valid", "invalid"]),
    id: z.string().uuid(),
    is_primary: z.boolean(),
    kind: SourceKind,
    latest_version: z.union([SourceVersionSummaryRead, z.null()]),
    name: z.string(),
    origin_type: SourceOrigin,
    project_id: z.string().uuid(),
    source_url: z.union([z.string(), z.null()]),
    version_count: z.number().int().gte(0),
  })
  .strict();
const SourcePageRead: z.ZodTypeAny = z
  .object({
    items: z.array(SourceSummaryRead),
    page: z.number().int().gte(1),
    page_size: z.number().int().gte(1).lte(100),
    total: z.number().int().gte(0),
  })
  .strict();
const SourceCreate: z.ZodTypeAny = z
  .object({
    is_primary: z.boolean().optional().default(false),
    kind: SourceKind,
    name: z.string().min(1).max(200),
    origin_type: SourceOrigin,
    source_url: z.union([z.string(), z.null()]).optional(),
  })
  .strict();
const SourceRead: z.ZodTypeAny = z
  .object({
    created_at: z.string().datetime({ offset: true }),
    id: z.string().uuid(),
    is_primary: z.boolean(),
    kind: SourceKind,
    name: z.string(),
    origin_type: SourceOrigin,
    project_id: z.string().uuid(),
    source_url: z.union([z.string(), z.null()]),
  })
  .strict();
const Body_create_upload_source_with_first_version_api_v1_projects__project_id__sources_upload_post: z.ZodTypeAny =
  z
    .object({
      file: z.string(),
      is_primary: z.boolean().optional().default(false),
      kind: SourceKind,
      name: z.string().min(1).max(200),
      source_id: z.string().uuid(),
    })
    .strict()
    .passthrough();
const SourceVersionRead: z.ZodTypeAny = z
  .object({
    byte_size: z.number().int(),
    content_sha256: z.string(),
    created_at: z.string().datetime({ offset: true }),
    created_by: z.string().uuid(),
    deduplicated: z.boolean().optional().default(false),
    detected_format: z.string(),
    id: z.string().uuid(),
    media_type: z.string(),
    source_etag: z.union([z.string(), z.null()]),
    source_id: z.string().uuid(),
    source_last_modified: z.union([z.string(), z.null()]),
  })
  .strict();
const SourceCreationRead: z.ZodTypeAny = z
  .object({ source: SourceRead, version: SourceVersionRead })
  .strict();
const SourceUrlCreate: z.ZodTypeAny = z
  .object({
    is_primary: z.boolean().optional().default(false),
    kind: SourceKind,
    name: z.string().min(1).max(200),
    source_id: z.string().uuid(),
    source_url: z.string().min(1).url(),
  })
  .strict();
const SourceUpdate: z.ZodTypeAny = z
  .object({
    is_primary: z.union([z.boolean(), z.null()]),
    name: z.union([z.string(), z.null()]),
  })
  .partial()
  .strict();
const SourceVersionPageRead: z.ZodTypeAny = z
  .object({
    items: z.array(SourceVersionRead),
    page: z.number().int().gte(1),
    page_size: z.number().int().gte(1).lte(100),
    total: z.number().int().gte(0),
  })
  .strict();
const Body_upload_source_version_api_v1_projects__project_id__sources__source_id__versions_post: z.ZodTypeAny =
  z.object({ file: z.string() }).strict().passthrough();
const ReadinessDependenciesRead: z.ZodTypeAny = z
  .object({
    artifact_storage: z.boolean(),
    build_queue: z.boolean(),
    milvus: z.boolean(),
    openrouter: z.boolean(),
    postgres: z.boolean(),
    redis: z.boolean(),
  })
  .strict();
const ReadinessRead: z.ZodTypeAny = z
  .object({ dependencies: ReadinessDependenciesRead, ready: z.boolean() })
  .strict();
const SystemSettingsRead: z.ZodTypeAny = z
  .object({
    build_concurrency: z.number().int(),
    build_retention_count: z.union([z.number(), z.null()]),
    builders_can_deploy: z.boolean(),
    environment: z.enum(["development", "production", "test"]),
    max_document_chunks_per_project: z.number().int(),
    max_operations_per_project: z.number().int(),
    max_upload_bytes: z.number().int(),
    mcp_base_domain: z.string(),
    source_retention_days: z.union([z.number(), z.null()]),
  })
  .strict();
const SystemSettingsUpdate: z.ZodTypeAny = z
  .object({
    build_concurrency: z.union([z.number(), z.null()]),
    build_retention_count: z.union([z.number(), z.null()]),
    builders_can_deploy: z.union([z.boolean(), z.null()]),
    environment: z.union([
      z.enum(["development", "production", "test"]),
      z.null(),
    ]),
    max_document_chunks_per_project: z.union([z.number(), z.null()]),
    max_operations_per_project: z.union([z.number(), z.null()]),
    max_upload_bytes: z.union([z.number(), z.null()]),
    mcp_base_domain: z.union([z.string(), z.null()]),
    source_retention_days: z.union([z.number(), z.null()]),
  })
  .partial()
  .strict();
const ModelSettingsRead: z.ZodTypeAny = z
  .object({
    analysis_model: z.union([z.string(), z.null()]),
    embedding_dimensions: z.union([z.number(), z.null()]),
    embedding_model: z.union([z.string(), z.null()]),
    include_documentation_in_analysis: z.boolean(),
    openrouter_configured: z.boolean(),
    updated_at: z.union([z.string(), z.null()]),
    validation_model: z.union([z.string(), z.null()]),
  })
  .strict();
const ModelSettingsUpdate: z.ZodTypeAny = z
  .object({
    analysis_model: z.union([z.string(), z.null()]),
    embedding_model: z.union([z.string(), z.null()]),
    include_documentation_in_analysis: z.boolean().default(false),
    validation_model: z.union([z.string(), z.null()]),
  })
  .partial()
  .strict();
const ModelCatalogItem: z.ZodTypeAny = z
  .object({
    context_length: z.union([z.number(), z.null()]).optional(),
    id: z.string(),
    name: z.string(),
    supports_embeddings: z.boolean(),
    supports_structured_outputs: z.boolean(),
  })
  .strict();
const OpenRouterSecretUpdate: z.ZodTypeAny = z
  .object({ api_key: z.string().min(10).max(500) })
  .strict();
const OpenRouterTestResult: z.ZodTypeAny = z
  .object({ message: z.string(), ok: z.boolean() })
  .strict();
const SourceIssueRead: z.ZodTypeAny = z
  .object({
    code: z.string(),
    column: z.union([z.number(), z.null()]).optional(),
    details: JsonObject,
    line: z.union([z.number(), z.null()]).optional(),
    message: z.string(),
    pointer: z.union([z.string(), z.null()]).optional(),
    severity: z.enum(["error", "warning", "info"]),
    source_version_id: z.string().uuid(),
    stage: z.string(),
  })
  .strict();
const IndexGenerationStatus: z.ZodTypeAny = z.enum([
  "building",
  "ready",
  "failed",
]);
const SourceVersionMetadataRead: z.ZodTypeAny = z
  .object({
    auth_schemes: z.array(z.string()),
    byte_size: z.number().int(),
    content_sha256: z.string(),
    created_at: z.string().datetime({ offset: true }),
    created_by: z.string().uuid(),
    deduplicated: z.boolean().optional().default(false),
    detected_format: z.string(),
    embedding_dimensions: z.union([z.number(), z.null()]),
    embedding_model: z.union([z.string(), z.null()]),
    errors: z.array(SourceIssueRead),
    id: z.string().uuid(),
    index_generation_id: z.union([z.string(), z.null()]),
    index_status: z.union([IndexGenerationStatus, z.null()]),
    indexed_chunk_count: z.union([z.number(), z.null()]),
    media_type: z.string(),
    metadata_build_id: z.union([z.string(), z.null()]),
    operation_count: z.union([z.number(), z.null()]),
    parse_status: z.enum(["pending", "valid", "invalid"]),
    preview_markdown: z.union([z.string(), z.null()]),
    servers: z.array(z.string()),
    source_etag: z.union([z.string(), z.null()]),
    source_id: z.string().uuid(),
    source_last_modified: z.union([z.string(), z.null()]),
    spec_version: z.union([z.string(), z.null()]),
  })
  .strict();
const UserCreate: z.ZodTypeAny = z
  .object({
    display_name: z.string().min(1).max(160),
    email: z.string().email(),
    password: z.string().min(12).max(1024),
    role: UserRole,
  })
  .strict();
const UserUpdate: z.ZodTypeAny = z
  .object({
    display_name: z.union([z.string(), z.null()]),
    is_active: z.union([z.boolean(), z.null()]),
    password: z.union([z.string(), z.null()]),
    role: z.union([UserRole, z.null()]),
  })
  .partial()
  .strict();

export const schemas = {
  actor,
  AuditEventRead,
  AuditPage,
  ValidationError,
  HTTPValidationError,
  LoginRequest,
  UserRole,
  UserRead,
  AuthResponse,
  BuildAdmissionState,
  BuildStatus,
  QueuedBuildAdmissionRead,
  BuildAdmissionOverviewRead,
  status,
  BuildTrigger,
  BuildRead,
  BuildPageRead,
  BuildMetricsRead,
  BuildAIRunRead,
  OperationChangeRead,
  BuildDiffRead,
  AuthProfile,
  BuildMetadata,
  ManifestProject,
  JsonScalar,
  JsonValue,
  MCPResource,
  RuntimeSecurity,
  ServerDefinition,
  JsonObject,
  MultipartFileMapping,
  RequestBodyMapping,
  HttpMethod,
  ParameterTarget,
  ParameterMapping,
  RequestMapping,
  ResponseDefinition,
  MCPTool,
  MCPManifest,
  method,
  OperationPageItemRead,
  OperationPageRead,
  FindingSeverity,
  ValidationSourceRefRead,
  ValidationFindingRead,
  ValidationStatus,
  ValidationReportRead,
  CleanupJobKind,
  CleanupJobStatus,
  CleanupJobRead,
  DeploymentActivationPhase,
  DeploymentStatus,
  DeploymentRead,
  HealthRead,
  RuntimeEffectState,
  ProjectRead,
  ProjectCreate,
  ProjectUpdate,
  BuildCreate,
  CredentialScheme,
  CredentialRead,
  CredentialSecretInput,
  CredentialCreate,
  CredentialRotate,
  DeploymentPageRead,
  DeploymentCreate,
  MCPAuthMode,
  SourceKind,
  JourneySourceRecord,
  JourneyStepState,
  JourneyStepRecord,
  ProjectJourneyRead,
  MCPAuthConfigRead,
  MCPAccessTokenRead,
  MCPAccessRead,
  MCPAuthConfigUpdate,
  MCPAccessStatusRead,
  MCPAccessTokenCreate,
  MCPAccessTokenIssued,
  MCPAccessTokenRotate,
  OperationExclusionRead,
  OperationExclusionCreate,
  DeploymentRollback,
  OperationServerRoutingRead,
  OperationSecurityRequirementRead,
  SecuritySchemeDiscoveryRead,
  ServerCandidateRead,
  SourceConfigurationDiscoveryRead,
  SourceVersionSummaryRead,
  SourceOrigin,
  SourceSummaryRead,
  SourcePageRead,
  SourceCreate,
  SourceRead,
  Body_create_upload_source_with_first_version_api_v1_projects__project_id__sources_upload_post,
  SourceVersionRead,
  SourceCreationRead,
  SourceUrlCreate,
  SourceUpdate,
  SourceVersionPageRead,
  Body_upload_source_version_api_v1_projects__project_id__sources__source_id__versions_post,
  ReadinessDependenciesRead,
  ReadinessRead,
  SystemSettingsRead,
  SystemSettingsUpdate,
  ModelSettingsRead,
  ModelSettingsUpdate,
  ModelCatalogItem,
  OpenRouterSecretUpdate,
  OpenRouterTestResult,
  SourceIssueRead,
  IndexGenerationStatus,
  SourceVersionMetadataRead,
  UserCreate,
  UserUpdate,
};

// The existing HTTP client owns cookies, CSRF, and refresh semantics. Export
// only generated success-response validators so every endpoint can validate
// its wire payload without creating a parallel generated client.
export const endpointResponses = {
  "get /api/v1/audit": AuditPage,
  "post /api/v1/auth/login": AuthResponse,
  "post /api/v1/auth/logout": z.void(),
  "get /api/v1/auth/me": UserRead,
  "post /api/v1/auth/refresh": AuthResponse,
  "get /api/v1/build-admission": BuildAdmissionOverviewRead,
  "get /api/v1/builds": BuildPageRead,
  "get /api/v1/builds/:build_id": BuildRead,
  "get /api/v1/builds/:build_id/ai-runs": z.array(BuildAIRunRead),
  "post /api/v1/builds/:build_id/cancel": BuildRead,
  "get /api/v1/builds/:build_id/diff": BuildDiffRead,
  "get /api/v1/builds/:build_id/events": z.unknown(),
  "get /api/v1/builds/:build_id/export": z.unknown(),
  "get /api/v1/builds/:build_id/manifest": MCPManifest,
  "get /api/v1/builds/:build_id/manifest/download": z.unknown(),
  "get /api/v1/builds/:build_id/operations": OperationPageRead,
  "get /api/v1/builds/:build_id/validation": ValidationReportRead,
  "get /api/v1/builds/metrics": BuildMetricsRead,
  "get /api/v1/cleanup-jobs": z.array(CleanupJobRead),
  "get /api/v1/cleanup-jobs/:job_id": CleanupJobRead,
  "get /api/v1/deployments/:deployment_id": DeploymentRead,
  "get /api/v1/deployments/:deployment_id/events": z.unknown(),
  "post /api/v1/deployments/:deployment_id/restart": DeploymentRead,
  "post /api/v1/deployments/:deployment_id/stop": DeploymentRead,
  "get /api/v1/health": HealthRead,
  "get /api/v1/projects": z.array(ProjectRead),
  "post /api/v1/projects": ProjectRead,
  "delete /api/v1/projects/:project_id": CleanupJobRead,
  "get /api/v1/projects/:project_id": ProjectRead,
  "patch /api/v1/projects/:project_id": ProjectRead,
  "get /api/v1/projects/:project_id/builds": BuildPageRead,
  "post /api/v1/projects/:project_id/builds": BuildRead,
  "get /api/v1/projects/:project_id/credentials": z.array(CredentialRead),
  "post /api/v1/projects/:project_id/credentials": CredentialRead,
  "delete /api/v1/projects/:project_id/credentials/:credential_id":
    CredentialRead,
  "post /api/v1/projects/:project_id/credentials/:credential_id/rotate":
    CredentialRead,
  "get /api/v1/projects/:project_id/deployments": DeploymentPageRead,
  "post /api/v1/projects/:project_id/deployments": DeploymentRead,
  "get /api/v1/projects/:project_id/journey": ProjectJourneyRead,
  "get /api/v1/projects/:project_id/mcp-access": MCPAccessRead,
  "put /api/v1/projects/:project_id/mcp-access/auth-mode": MCPAuthConfigRead,
  "get /api/v1/projects/:project_id/mcp-access/status": MCPAccessStatusRead,
  "post /api/v1/projects/:project_id/mcp-access/tokens": MCPAccessTokenIssued,
  "delete /api/v1/projects/:project_id/mcp-access/tokens/:token_id":
    MCPAccessTokenRead,
  "post /api/v1/projects/:project_id/mcp-access/tokens/:token_id/rotate":
    MCPAccessTokenIssued,
  "get /api/v1/projects/:project_id/operation-exclusions": z.array(
    OperationExclusionRead,
  ),
  "post /api/v1/projects/:project_id/operation-exclusions":
    OperationExclusionRead,
  "delete /api/v1/projects/:project_id/operation-exclusions/:exclusion_id":
    z.void(),
  "post /api/v1/projects/:project_id/rebuild": BuildRead,
  "post /api/v1/projects/:project_id/review": BuildRead,
  "post /api/v1/projects/:project_id/rollback": DeploymentRead,
  "get /api/v1/projects/:project_id/source-configuration":
    SourceConfigurationDiscoveryRead,
  "get /api/v1/projects/:project_id/sources": SourcePageRead,
  "post /api/v1/projects/:project_id/sources": SourceRead,
  "delete /api/v1/projects/:project_id/sources/:source_id": CleanupJobRead,
  "patch /api/v1/projects/:project_id/sources/:source_id": SourceRead,
  "post /api/v1/projects/:project_id/sources/:source_id/refresh":
    SourceVersionRead,
  "get /api/v1/projects/:project_id/sources/:source_id/versions":
    SourceVersionPageRead,
  "post /api/v1/projects/:project_id/sources/:source_id/versions":
    SourceVersionRead,
  "post /api/v1/projects/:project_id/sources/upload": SourceCreationRead,
  "post /api/v1/projects/:project_id/sources/url": SourceCreationRead,
  "get /api/v1/ready": ReadinessRead,
  "get /api/v1/settings": SystemSettingsRead,
  "patch /api/v1/settings": SystemSettingsRead,
  "get /api/v1/settings/models": ModelSettingsRead,
  "put /api/v1/settings/models": ModelSettingsRead,
  "get /api/v1/settings/models/catalog": z.array(ModelCatalogItem),
  "put /api/v1/settings/openrouter": ModelSettingsRead,
  "post /api/v1/settings/openrouter/test": OpenRouterTestResult,
  "get /api/v1/source-versions/:version_id/metadata": SourceVersionMetadataRead,
  "get /api/v1/users": z.array(UserRead),
  "post /api/v1/users": UserRead,
  "patch /api/v1/users/:user_id": UserRead,
};
