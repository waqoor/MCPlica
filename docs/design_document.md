# MCPlica Design Document

**Status:** Authoritative implementation specification  
**Date:** 2026-08-24  
**Applies to:** Builder/control-plane internals and the generic MCP runtime

## 1. Document ownership

This document owns the **technical design**: repository/module structure, internal interfaces, service/client/repository patterns, database/domain models, REST APIs, schemas, state machines, build logic, compiler rules, runtime behavior, security controls, failure handling, observability, and test seams.

Architectural boundaries are owned by `architecture.md`; product behavior and scope by `product_requirements.md`; technology/version choices by `tech_stack.md`; execution order by `implementation_plan.md`; legal/governance rules by `open_source_and_sponsorship_model.md`.

---

## 2. Design principles

The implementation must follow these rules throughout the codebase:

1. **Thin transport, explicit services.** FastAPI routers validate/authorize/dispatch; they do not implement domain logic.
2. **Clients own SDK/transport details.** No service directly creates a Redis, Milvus, Docker, OpenRouter, or raw HTTP client.
3. **Repositories own persistence queries.** Domain services do not contain ad hoc SQLAlchemy statements outside repository modules.
4. **Pydantic models define cross-boundary data contracts.** API payloads, canonical API models, AI structured output, manifests, config, and runtime inputs use explicit models.
5. **Immutable source/build artifacts.** Updates create versions; completed build data is not modified in place.
6. **Deterministic executable mappings.** AI-generated semantic data can be accepted only into explicitly non-executable fields unless corroborated by source data and compiler rules.
7. **No hidden dynamic code execution.** Never `eval`, `exec`, import user-supplied Python, execute uploaded scripts, or generate arbitrary Python code as build output.
8. **Fail closed.** Unknown auth schemes, unresolved `$ref`, unsupported executable schema constructs, invalid mappings, and secret failures are blocking unless an operation is explicitly excluded with a visible reason.
9. **Idempotent background jobs.** Build/deploy operations use durable IDs and safe retry behavior.
10. **Secrets never enter normal serialized domain models.** Secret values use dedicated secret input types and redacted representations.

---

## 3. Repository layout

The repository shall be a monorepo with these root areas:

```text
/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   ├── core/
│   │   ├── clients/
│   │   ├── providers/
│   │   ├── repositories/
│   │   ├── services/
│   │   ├── domain/
│   │   ├── parsers/
│   │   ├── compilers/
│   │   ├── validators/
│   │   ├── jobs/
│   │   ├── prompts/
│   │   └── models/
│   ├── tests/
│   └── pyproject.toml
│
├── mcp_runtime/
│   ├── app/
│   │   ├── main.py
│   │   ├── server/
│   │   ├── manifest/
│   │   ├── executor/
│   │   ├── clients/
│   │   ├── auth/
│   │   ├── security/
│   │   ├── validation/
│   │   ├── observability/
│   │   └── core/
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   │   └── ui/
│   │   ├── features/
│   │   ├── hooks/
│   │   ├── lib/
│   │   ├── pages/
│   │   ├── routes/
│   │   └── types/
│   ├── tests/
│   ├── package.json
│   └── vite.config.ts
│
├── packages/
│   └── contracts/
│       ├── src/mcp_contracts/
│       ├── tests/
│       └── pyproject.toml
├── migrations/
│   └── alembic/
├── infra/
│   ├── compose.yaml
│   ├── traefik/
│   ├── milvus/
│   └── docker/
├── docs/
├── scripts/
├── tests/
│   ├── e2e/
│   ├── fixtures/
│   └── integration/
├── pyproject.toml
├── uv.lock
└── pnpm-lock.yaml
```

The exact repository name is irrelevant to behavior; these module boundaries are not.

---

## 4. Backend layering

### 4.1 API layer

Location: `backend/app/api/`

Responsibilities:

- parse HTTP request;
- enforce authentication/role;
- validate DTOs;
- call one or more application service methods;
- translate known domain errors to versioned API errors;
- never issue raw infrastructure calls.

API prefix: `/api/v1`.

### 4.2 Service layer

Location: `backend/app/services/`

Services own use cases and transactions. Each service receives dependencies by constructor/factory injection.

Core services:

- `AuthService`
- `UserService`
- `ProjectService`
- `SourceService`
- `CredentialService`
- `DocumentationService`
- `IndexingService`
- `AnalysisService`
- `GenerationService`
- `CompilationService`
- `ValidationService`
- `BuildService`
- `BuildDiffService`
- `DeploymentService`
- `McpAccessService`
- `ExportService`
- `AuditService`
- `SystemSettingsService`

### 4.3 Domain layer

Location: `backend/app/domain/`

Contains infrastructure-independent models/enums/value objects for:

- Project
- Source
- Canonical API
- Build
- MCP definition/manifest
- Validation
- Deployment
- Credentials metadata
- MCP access metadata

No SQLAlchemy model or SDK object may leak into domain interfaces.

### 4.4 Repository layer

Location: `backend/app/repositories/`

Repositories encapsulate all domain persistence queries.

Examples:

- `UserRepository`
- `ProjectRepository`
- `SourceRepository`
- `CanonicalSnapshotRepository`
- `BuildRepository`
- `ValidationRepository`
- `CredentialRepository`
- `DeploymentRepository`
- `AuditRepository`
- `SettingsRepository`

Repositories accept a transaction/session abstraction from `DatabaseClient` and return domain/record models, not raw SQL rows.

### 4.5 Clients

Location: `backend/app/clients/`

Required clients:

```text
clients/
├── base/
│   ├── client.py
│   ├── exceptions.py
│   ├── retry.py
│   └── health.py
├── database/postgres_client.py
├── cache/redis_client.py
├── vector/milvus_client.py
├── ai/openrouter_client.py
├── http/http_client.py
├── docker/docker_client.py
├── mcp/mcp_client.py
└── storage/filesystem_client.py
```

Clients own connection lifecycle, low-level SDK invocation, timeouts, transport errors, health checking, and conversion into project-defined client exceptions.

### 4.6 Providers/adapters

Location: `backend/app/providers/`

Provider interfaces represent semantic capabilities that may have alternative implementations later.

Required interfaces:

```python
class AIProvider(Protocol):
    async def structured_generate(...): ...
    async def embed(...): ...
    async def list_models(...): ...

class VectorStore(Protocol):
    async def ensure_index(...): ...
    async def upsert_chunks(...): ...
    async def search(...): ...
    async def delete_generation(...): ...

class ArtifactStorage(Protocol):
    async def put(...): ...
    async def get(...): ...
    async def delete(...): ...
```

Initial implementations:

- `OpenRouterProvider`
- `MilvusVectorStore`
- `FilesystemArtifactStorage`

A provider may call one or more dedicated clients; services depend on provider interfaces where semantics matter.

---

## 5. Dependency injection and application lifecycle

`backend/app/main.py` shall create the FastAPI application through an application factory.

The lifespan acquires shared clients once per process through one transactional async exit stack:

- database engine/pool;
- Redis pool;
- Milvus connection/provider;
- shared `httpx.AsyncClient` via `HttpClient`;
- OpenRouter provider when configured;
- filesystem storage;
- service container/factories.

The web API process shall **not** initialize `DockerClient` unless it is executing in a dedicated deployment-worker profile. Normal web processes cannot possess Docker Engine authority.

Every successful acquisition registers its close action immediately. Startup failure closes all
previously acquired resources; shutdown signals every dispatcher, waits only for the configured
bounded grace period, cancels overdue tasks, and still attempts every client close. Clients expose
`close()`/context lifecycle and health methods. Constructing the API's Milvus client is lazy and
must not make control-plane startup depend on a live Milvus service.

---

## 6. Installation-level users and permissions

The platform is not multi-tenant, but it still requires local installation access control.

### 6.1 Roles

Two roles are sufficient:

- `ADMIN`
- `BUILDER`

`ADMIN` can:

- manage users;
- manage system/OpenRouter settings;
- create/edit/delete all projects;
- configure/rotate target API credentials;
- create/rotate/revoke MCP access credentials;
- build/rebuild;
- deploy/rollback/stop/delete deployments;
- view audit events;
- manage system-level retention/settings.

`BUILDER` can:

- create/edit projects;
- upload and version sources/documents;
- start analysis/build/review/rebuild;
- inspect operations/manifests/validation;
- deploy or redeploy only if an installation setting `builders_can_deploy=true` is enabled;
- cannot reveal/rotate target API secrets;
- cannot manage users/system secret settings.

There is no organization/tenant membership model.

### 6.2 Authentication

Local authentication uses email/username plus Argon2 password hashing.

Argon2 hashing and verification run in a worker thread rather than on the asynchronous event loop.
Role/active mutations serialize in PostgreSQL and the last-administrator invariant counts active
administrators only.

Session design:

- short-lived signed access token stored in `HttpOnly`, `Secure`, `SameSite=Lax` cookie;
- refresh/session record stored server-side with hashed opaque refresh token and revocation state;
- CSRF token required for state-changing browser requests when cookie auth is used;
- explicit logout revokes the session;
- password changes revoke existing sessions;
- first-run bootstrap creates the first administrator only when no users exist and a bootstrap secret/CLI command is used.

Public registration does not exist.

---

## 7. Database design

PostgreSQL is authoritative. Use UUID primary keys and UTC timestamps.

### 7.1 `users`

Required fields:

- `id UUID PK`
- `email CITEXT UNIQUE NOT NULL`
- `display_name TEXT NOT NULL`
- `password_hash TEXT NOT NULL`
- `role ENUM(admin,builder) NOT NULL`
- `is_active BOOLEAN NOT NULL DEFAULT true`
- `created_at TIMESTAMPTZ`
- `updated_at TIMESTAMPTZ`
- `last_login_at TIMESTAMPTZ NULL`

### 7.2 `auth_sessions`

- `id UUID PK`
- `user_id FK users`
- `refresh_token_hash TEXT UNIQUE`
- `expires_at TIMESTAMPTZ`
- `revoked_at TIMESTAMPTZ NULL`
- `created_at`
- `last_used_at`
- `user_agent_hash TEXT NULL`
- `ip_prefix INET NULL` (optional audit metadata, not a hard binding)

### 7.3 `projects`

- `id UUID PK`
- `name TEXT NOT NULL`
- `slug TEXT UNIQUE NOT NULL`
- `description TEXT NULL`
- `default_base_url TEXT NULL`
- `mcp_hostname TEXT UNIQUE NOT NULL`
- `is_enabled BOOLEAN NOT NULL DEFAULT true`
- `active_build_id UUID NULL`
- `active_deployment_id UUID NULL`
- `created_by UUID FK users`
- `created_at`
- `updated_at`

Slug rules:

- lowercase ASCII letters/digits/hyphens;
- 3-63 chars;
- starts/ends alphanumeric;
- globally unique in the installation;
- immutable after first successful deployment unless the old hostname is explicitly retired.

### 7.4 `project_sources`

Represents logical source slots.

- `id UUID PK`
- `project_id FK`
- `kind ENUM(openapi,api_inventory,documentation)`
- `name TEXT`
- `origin_type ENUM(upload,url)`
- `source_url TEXT NULL`
- `is_primary BOOLEAN`
- `current_version_id UUID NULL` referencing a version owned by the same source
- `current_version_selected_at TIMESTAMPTZ NULL`
- `last_observed_at TIMESTAMPTZ NULL`
- `last_observed_etag TEXT NULL`
- `last_observed_last_modified TEXT NULL`
- `created_at`

At least one `openapi` or `api_inventory` source must be present for a build.
Current selection, latest observation metadata, and accepted HTTP validators move transactionally
together; consumers do not infer current content from version creation order.

### 7.5 `source_versions`

Immutable.

- `id UUID PK`
- `source_id FK`
- `content_sha256 CHAR(64)`
- `media_type TEXT`
- `storage_key TEXT`
- `byte_size BIGINT`
- `detected_format TEXT`
- `source_etag TEXT NULL`
- `source_last_modified TEXT NULL`
- `created_by UUID`
- `created_at`

Unique constraint: `(source_id, content_sha256)`.

### 7.6 `project_credentials`

Stores secret metadata and encrypted payload.

- `id UUID PK`
- `project_id FK`
- `name TEXT`
- `scheme_type TEXT`
- `encrypted_payload BYTEA NOT NULL`
- `key_version TEXT NOT NULL`
- `metadata JSONB NOT NULL DEFAULT {}`
- `created_by UUID`
- `created_at`
- `rotated_at NULL`
- `revoked_at NULL`

Plaintext secret fields are never returned from repository reads after creation except through an explicit internal decrypt method available only to authorized execution paths.

`metadata` carries the validated source-security binding (for example scheme identity and
API-key name/location). That binding is immutable during secret rotation. Rotation uses optimistic
concurrency and replaces only encrypted secret material; a binding change requires a replacement
credential and a new Build. Current source discovery is required when establishing the binding,
not when rotating a still-valid stored binding after source drift.

### 7.7 `canonical_snapshots`

Immutable per build input.

- `id UUID PK`
- `project_id FK`
- `schema_version TEXT`
- `canonical_sha256 CHAR(64)`
- `canonical_json JSONB NOT NULL`
- `source_version_ids UUID[]` or normalized join table
- `created_at`

For large documents, `canonical_json` may move to artifact storage while PostgreSQL retains metadata/hash; this is an implementation optimization that must preserve the domain contract.

### 7.8 `builds`

- `id UUID PK`
- `project_id FK`
- `sequence INTEGER NOT NULL`
- `status build_status NOT NULL`
- `trigger ENUM(initial,source_change,manual_review,manual_rebuild)`
- `canonical_snapshot_id UUID NULL`
- `previous_build_id UUID NULL`
- `compiler_version TEXT`
- `manifest_schema_version TEXT`
- `runtime_compatibility TEXT`
- `analysis_model TEXT NULL`
- `validation_model TEXT NULL`
- `embedding_model TEXT NULL`
- `embedding_dimensions INTEGER NULL`
- `prompt_bundle_version TEXT NULL`
- `manifest_sha256 CHAR(64) NULL`
- `artifact_sha256 CHAR(64) NULL`
- `manifest_storage_key TEXT NULL`
- `artifact_storage_key TEXT NULL`
- `error_code TEXT NULL`
- `error_summary TEXT NULL`
- `pipeline_stage TEXT NOT NULL`
- `executable_configuration_sha256 CHAR(64)`
- `admission_token UUID NULL`
- `admission_lease_expires_at TIMESTAMPTZ NULL`
- `cancellation_requested_at TIMESTAMPTZ NULL`
- `cancellation_acknowledged_at TIMESTAMPTZ NULL`
- `requested_by UUID`
- `created_at`
- `started_at NULL`
- `completed_at NULL`

Unique `(project_id, sequence)`.

### 7.9 `build_source_versions`

Join table binding a Build to exact source versions.

- `build_id`
- `source_version_id`
- frozen `source_id`, kind, name, origin, URL, creation time, and primary role
- `dependency_aliases JSONB`
- `binding_metadata_trustworthy BOOLEAN`
- composite PK

New Builds use only this frozen executable identity. Migration-backfilled historical bindings are
not marked trustworthy when their original role/aliases cannot be proven and cannot be newly
activated until rebuilt.

### 7.10 `build_ai_runs`

Stores build-time AI audit, not chain-of-thought.

- `id UUID PK`
- `build_id FK`
- `stage TEXT`
- `provider TEXT` = `openrouter`
- `model TEXT`
- `prompt_template_id TEXT`
- `prompt_template_version TEXT`
- `input_context_sha256`
- `retrieved_chunk_ids JSONB`
- `response_schema_id TEXT`
- `response_sha256`
- `usage_json JSONB NULL`
- `cost_json JSONB NULL`
- `latency_ms INTEGER NULL`
- `status TEXT`
- `error_code TEXT NULL`
- `created_at`

Store validated structured output or its artifact reference when needed for reproducibility; do not store hidden model reasoning.
Usage/cost evidence includes every accepted, schema-rejected, and transport-failed structured
attempt exactly once. A response is validated before a run becomes successful or reusable; an
invalid historical success is atomically demoted and regenerated.

### 7.11 `document_index_generations`

- `id UUID PK`
- `project_id FK`
- `build_id FK`
- `embedding_model TEXT`
- `dimensions INTEGER`
- `collection_name TEXT`
- `generation_key TEXT`
- `chunk_count INTEGER`
- `source_fingerprint CHAR(64)`
- `status TEXT`
- `execution_token UUID NULL`
- `created_at`

For a fenced Build, the accepted execution token is part of generation ownership and of the
physical Milvus row identity/filter. The deterministic canonical chunk ID remains metadata and the
embedding-cache key remains content-based.

### 7.12 `validation_reports`

- `id UUID PK`
- `build_id UNIQUE FK`
- `overall_status ENUM(pass,fail)`
- `operation_source_count INTEGER`
- `operation_excluded_count INTEGER`
- `operation_expected_count INTEGER`
- `operation_generated_count INTEGER`
- `coverage_percent NUMERIC(5,2)`
- `blocking_error_count INTEGER`
- `warning_count INTEGER`
- `report_json JSONB`
- `created_at`

### 7.13 `operation_exclusions`

Explicit exclusions only.

- `id UUID PK`
- `build_id FK`
- `operation_key TEXT`
- `reason_code TEXT`
- `reason TEXT`
- `is_user_requested BOOLEAN`
- `created_at`

No operation may silently disappear.

### 7.14 `deployments`

- `id UUID PK`
- `project_id FK`
- `build_id FK`
- `intent ENUM(normal,security_refresh,rollback)`
- `status deployment_status`
- `hostname TEXT`
- `container_name TEXT`
- `container_id TEXT NULL`
- `image_ref TEXT`
- `image_digest TEXT NULL`
- `network_name TEXT`
- `manifest_sha256 TEXT`
- `health_status TEXT NULL`
- `deployed_by UUID`
- `created_at`
- `started_at NULL`
- `stopped_at NULL`
- `failed_at NULL`
- `error_code TEXT NULL`
- `error_summary TEXT NULL`

Only one deployment may be active for a project hostname at a time.

Runtime lifecycle commands and cleanup targets each carry a per-attempt execution token plus a
database-time lease while running. Terminal writes require the exact unexpired token. Runtime
effects additionally hold the project advisory lock and respect predecessor sequence; cleanup
targets lock their parent job before aggregate refresh and claim immediately before external work.

### 7.15 `mcp_auth_configs`

One row per Project when configured.

- `project_id UUID PK/FK projects`
- `mode ENUM(static_bearer,external_oauth_oidc,disabled_dev)`
- `issuer_url TEXT NULL`
- `audiences JSONB NOT NULL DEFAULT []`
- `required_scopes JSONB NOT NULL DEFAULT []`
- `metadata JSONB NOT NULL DEFAULT {}`
- `updated_by UUID`
- `updated_at`

`disabled_dev` is rejected when the installation is not explicitly in development mode. Static bearer token hashes remain in `mcp_access_tokens`; OAuth/OIDC public verifier metadata belongs here and secrets are not required for normal JWKS resource-server validation.

### 7.16 `mcp_access_tokens`

- `id UUID PK`
- `project_id FK`
- `name TEXT`
- `token_prefix TEXT`
- `token_hash TEXT`
- `created_by UUID`
- `created_at`
- `expires_at NULL`
- `last_used_at NULL` (if reporting is enabled)
- `revoked_at NULL`

Token plaintext is shown only once at creation/rotation.

### 7.17 `system_settings`

Non-secret settings only.

- `key TEXT PK`
- `value_json JSONB`
- `updated_by UUID`
- `updated_at`

Secrets such as the OpenRouter API key use the encrypted secret mechanism/environment secrets, not plain settings rows.

### 7.18 `audit_events`

Append-only.

- `id UUID PK`
- `actor_user_id UUID NULL`
- `event_type TEXT`
- `entity_type TEXT`
- `entity_id UUID NULL`
- `project_id UUID NULL`
- `request_id TEXT NULL`
- `metadata JSONB`
- `created_at`

No secret values or raw sensitive payloads in metadata.

---

## 8. Canonical API model

The canonical representation is versioned, for example `canonical-api/v1`.

### 8.1 Root model

Conceptual Pydantic shape:

```python
class CanonicalApiDefinition(BaseModel):
    schema_version: Literal["canonical-api/v1"]
    project_id: UUID
    title: str
    version: str | None
    description: str | None
    servers: list[CanonicalServer]
    security_schemes: dict[str, CanonicalSecurityScheme]
    schemas: dict[str, JsonSchemaDocument]
    operations: list[CanonicalOperation]
    documentation_refs: list[DocumentationRef]
    provenance: CanonicalProvenance
```

### 8.2 Operation model

```python
class CanonicalOperation(BaseModel):
    key: str
    source_operation_id: str | None
    tool_name_seed: str
    method: HttpMethod
    path_template: str
    server_ref: str
    summary: str | None
    description: str | None
    parameters: list[CanonicalParameter]
    request_body: CanonicalRequestBody | None
    responses: list[CanonicalResponse]
    security: list[CanonicalSecurityRequirement]
    tags: list[str]
    semantic: OperationSemanticMetadata
    provenance: OperationProvenance
```

`key` is deterministic and stable. Preferred key generation:

1. normalized OpenAPI `operationId` if unique and stable;
2. otherwise `METHOD + normalized path template` hashed/slugged in a deterministic manner.

### 8.3 Provenance

Every executable field must be traceable to a source path such as:

```text
source_version_id
json_pointer / YAML path
```

AI enrichment records its own separate provenance and may not replace the executable provenance.

The build configuration also freezes `runtime_manifest_max_bytes`. The validator compares this
limit to the byte length of the exact canonical serialization whose SHA-256 is persisted on the
Build; object estimates or pre-serialization character counts are not authoritative. Equality is
accepted. One excess byte is a blocking artifact finding and prevents `READY`. Deployment
preflight reads with `min(build_frozen_limit, current_runtime_limit)` and reports a stable
`MANIFEST_EXCEEDS_RUNTIME_LIMIT` denial rather than allowing a runtime startup failure.

Source repair evidence follows the same immutable identity rule. `source_findings` is keyed by
build, `source_version_id`, and a deterministic finding key so worker retries upsert rather than
duplicate evidence. It stores stage, stable code, severity, message, pointer, one-based line and
column, and redacted structured details. The source-version metadata endpoint reads only findings
for that exact version in the selected build; it must not project a build summary onto every bound
source.

---

## 9. API Inventory v1 format

The platform defines a documented alternative input format for APIs that do not have OpenAPI.

Root:

```yaml
schema: api-inventory/v1
name: Inventory Service
version: "1.0"
servers:
    - id: primary
      url: https://inventory.example.internal
security_schemes:
    bearerAuth:
        type: http_bearer
operations:
    - operation_id: getProduct
      method: GET
      path: /products/{product_id}
      summary: Get product
      description: Retrieve a product by ID.
      parameters:
          - name: product_id
            in: path
            required: true
            schema:
                type: string
      responses:
          "200":
              content_type: application/json
              schema:
                  type: object
                  additionalProperties: true
      security:
          - bearerAuth: []
```

Required rules:

- `schema` must equal `api-inventory/v1`;
- every operation requires method/path;
- path placeholders require matching required path parameters;
- request/response JSON Schemas follow supported JSON Schema semantics;
- executable hosts come only from declared servers/project configuration;
- documentation cannot fill a missing method/path.

The project shall publish a JSON Schema for this inventory format and validate imports against it.

---

## 10. Source ingestion design

### 10.1 Uploads

Upload handling:

1. stream to a temporary file;
2. enforce configurable byte limit before full ingestion;
3. calculate SHA-256 while streaming;
4. validate MIME/extension only as hints, then parse content safely;
5. move to immutable content-addressed storage path;
6. create `source_version` row transactionally;
7. never overwrite an existing blob.

ZIP archives are not accepted as executable source in V1. Documentation bundles may be added later only with zip-slip/bomb protections.
The reverse proxy, ASGI multipart guard, application upload limit, and temporary filesystem are one
capacity contract. The application reserves headroom for at least two concurrent boundary uploads
and rejects excess requests before Starlette can exhaust its spool filesystem.

### 10.2 Remote URLs

URL ingestion uses `HttpClient` with SSRF controls:

- HTTPS required by default;
- HTTP allowed only via explicit installation setting for private/internal environments;
- no arbitrary redirects;
- max redirects 3 after revalidation;
- allowed content size;
- connect/read timeouts plus one total deadline covering DNS/policy resolution, retries,
  redirects, and streamed body consumption;
- DNS/IP blocking rules;
- ETag/Last-Modified persisted when provided.

### 10.3 Source refresh

Refreshing a URL source creates a new version only if content hash changes.

---

## 11. OpenAPI parser and reference resolution

### 11.1 Supported input

- OpenAPI 3.0.x
- OpenAPI 3.1.x
- JSON and YAML

Swagger/OpenAPI 2.0 is out of core V1 scope; user must convert it first unless a later adapter is added.

### 11.2 `$ref` rules

- local refs are resolved;
- refs among uploaded project source files are allowed when explicitly linked;
- remote refs use the controlled source-fetch client and are captured as immutable source dependencies;
- circular schema references are allowed when representable but must be detected to prevent infinite expansion;
- the canonical model preserves refs/definitions where flattening would lose correctness;
- unresolved refs are blocking for affected executable operations.

### 11.3 Server selection

If the source defines multiple inherited/root servers, the project stores all candidates but requires an explicit active server mapping for deployment. That mapping resolves only ambiguous inherited candidates; explicit path- and operation-scoped OpenAPI servers remain bound to their operations. The compiler never lets an MCP caller choose an arbitrary server URL.

### 11.4 Unsupported constructs

Unsupported executable constructs produce operation-level blocking findings. A user may explicitly exclude affected operations; the validation report then counts and explains them.

---

## 12. Documentation parsing/indexing

Supported supplemental documentation in V1:

- JSON (`.json`)
- Markdown (`.md`)
- plain text (`.txt`)
- CSV (`.csv`)
- Excel Open XML (`.xlsx`)
- Word Open XML (`.docx`)
- HTML (`.html` or fetched HTML pages)
- PDF with extractable text

OCR is not part of V1. Image-only PDFs are reported as having insufficient extractable text.
Office Open XML packages are treated as untrusted archives: entry paths, encryption,
macros, entry count, expanded size, and compression ratio are validated before bounded
text extraction. Formulas and document code are never executed.

### 12.1 Normalization

Every document becomes:

```python
class NormalizedDocument(BaseModel):
    source_version_id: UUID
    title: str | None
    text: str
    sections: list[DocumentSection]
    metadata: dict[str, JsonValue]
```

### 12.2 Chunking

Chunking must preserve section/title/source provenance. Defaults are token-aware, with overlap only where useful. Chunk IDs are deterministic from source hash + normalized section path + chunk ordinal/content hash.

### 12.3 Embeddings

`OpenRouterProvider.embed()` receives batches and returns vectors plus model/dimension metadata. Embedding dimensionality is recorded and Milvus collections/index configuration must match it.

### 12.4 Milvus schema

At minimum each indexed row contains:

- `chunk_id`
- `project_id`
- `generation_id`
- `source_version_id`
- `source_kind`
- `title`
- `section_path`
- `operation_keys[]` when correlated
- `text`
- `content_sha256`
- `embedding`

Project/build filters must always be applied to searches to prevent cross-project retrieval.

---

## 13. OpenRouter analysis design

### 13.1 Configuration

The installation configures:

- analysis model;
- semantic validation model (may equal analysis model);
- embedding model;
- maximum context budget;
- maximum parallel OpenRouter requests;
- retry limits/timeouts;
- optional cost ceiling per build as a safety control, not a subscription mechanism.

A build cannot enter AI stages if required models are not configured/capable.

### 13.2 Structured outputs

Every build-changing AI call defines a strict response model.

Examples:

- `OperationEnrichmentResult`
- `OperationRelationshipResult`
- `DocumentationCorrelationResult`
- `SemanticValidationResult`

Responses must be validated by Pydantic before a successful AI-run/cache record is published.
Invalid structured output is retained as failed attempt evidence, retried within a bounded policy,
then fails the affected stage if still invalid. Tokens and provider cost from every attempt are
aggregated once even when the response is rejected.

### 13.3 Retrieval

AI prompts include only relevant source facts and retrieved document chunks. The retrieval query is based on operation name, path, source summary/description, tags, and relevant schema names.

Retrieved chunks are recorded by ID on `build_ai_runs`.

### 13.4 AI write boundary

AI may write only fields designated `semantic`/`enrichment`, for example:

- user-friendly title;
- improved description;
- business category;
- synonyms/keywords;
- documentation links;
- confidence/findings;
- non-executable relationship hints.

AI cannot write or mutate:

- HTTP method;
- upstream host;
- path template;
- parameter location/type/required status;
- request schema executable structure;
- response schema executable structure;
- security scheme type;
- secret values;
- operation enablement without a deterministic/user decision.

---

## 14. MCP manifest design

The authoritative manifest models and JSON Schema live in the infrastructure-free shared workspace package `packages/contracts/`. Both the backend compiler and `mcp_runtime` import this package; neither maintains a separate handwritten copy.

Manifest schema version: `mcp-manifest/v1`.

Conceptual root:

```json
{
  "schema_version": "mcp-manifest/v1",
  "manifest_id": "...",
  "project": {
    "id": "...",
    "name": "Inventory",
    "slug": "inventory"
  },
  "runtime_compatibility": ">=1.0.0-rc.1,<2.0",
  "servers": [...],
  "auth_profiles": [...],
  "tools": [...],
  "resources": [...],
  "security": {...},
  "build": {...}
}
```

### 14.1 Tool structure

Each tool includes:

- stable `name`;
- `title`;
- `description`;
- `input_schema` exact JSON Schema;
- optional `output_schema`/response metadata;
- `operation_key`;
- `request_mapping`;
- `security_profile_ref`;
- `timeout_ms`;
- `max_response_bytes`;
- `enabled`;
- provenance metadata not exposed as a secret.

### 14.2 Stable tool names

Rules:

1. Prefer normalized unique `operationId`.
2. Convert to lowercase snake_case or MCP-compatible normalized identifier.
3. If missing, derive from method + path semantics deterministically.
4. Resolve collisions with stable suffix derived from operation key, never random sequence numbers.
5. Tool names remain stable across rebuilds when the operation identity remains stable.

### 14.3 Parameter mapping

Tool input is one JSON object.

Compiler maps:

- path params -> named properties;
- query params -> named properties;
- headers -> named properties only when safe and explicitly declared; auth headers are excluded;
- request body -> `body` property by default when combining body with non-body parameters, or flattened only when deterministic rules prove no collision/loss;
- optional params remain optional;
- required source params remain required.

The manifest records exact location/serialization so the runtime never asks an LLM to infer placement.

### 14.4 Request body media types

V1 executable support must include:

- `application/json`
- `application/x-www-form-urlencoded`
- `multipart/form-data` for bounded file/field mappings only if the source schema is explicit

Unsupported media types block or exclude the operation visibly.

### 14.5 Responses

The runtime returns:

- structured JSON when upstream content type is JSON;
- bounded text when textual;
- metadata/error for unsupported/binary responses unless an explicit resource/file strategy is implemented.

Raw unbounded binary response forwarding is not core V1 behavior.

### 14.6 Resources

Documentation resources use stable URIs such as:

```text
docs://<project-slug>/<document-key>/<section-key>
```

Resource content is derived from normalized documentation and does not contain credentials.

---

## 15. Compiler correctness rules

For every non-excluded operation:

- method is identical to source;
- path template is semantically identical;
- required path params are present;
- query serialization is preserved for supported styles;
- required request body stays required;
- JSON Schema required/type/enum constraints are retained;
- security requirement mapping is explicit;
- no arbitrary caller-controlled base URL;
- tool description cannot claim capabilities absent from source;
- runtime mapping references a known server/auth profile;
- one stable operation key maps to one stable tool unless a documented exception is recorded.

Compiler output is canonicalized before hashing: stable key ordering, normalized UTF-8, deterministic arrays where order is not semantic.

---

## 16. Validation design

Validation findings use:

```python
class ValidationFinding(BaseModel):
    code: str
    severity: Literal["error", "warning", "info"]
    stage: str
    operation_key: str | None
    source_ref: SourceRef | None
    message: str
    details: dict[str, JsonValue]
```

### 16.1 Blocking conditions

Examples:

- invalid/unresolved executable source;
- generated tool count mismatch without exclusions;
- required parameter dropped;
- invalid JSON Schema;
- missing target auth configuration;
- manifest schema invalid;
- runtime compatibility mismatch;
- duplicate tool names;
- upstream host missing/not allowed;
- secret mapping unresolved;
- MCP runtime cannot initialize or list generated tools/resources in the validation harness;
- any enabled tool lacks schema-valid representative arguments or cannot complete a successful
  schema-valid call through the production runtime factory;
- actual upstream success status, media type, decoded body, or deterministic MCP response
  envelope violates the compiled response contract.

Warnings may include sparse descriptions or weak documentation correlation but must not conceal structural failures.

The harness must not substitute a synthetic failure response merely to reach an executor path.
Probe construction is performed before startup, all enabled tools are called with the official
client, MCP `is_error` results are blocking, and teardown remains bounded even when one probe
fails.

### 16.2 Coverage metrics

```text
source_operations
excluded_operations
expected_operations = source_operations - excluded_operations
generated_tools
coverage = generated_tools / expected_operations * 100
```

A build requires 100% expected operation coverage unless a future explicitly documented mode changes this rule.

---

## 17. Build state machine

Canonical build statuses:

```text
QUEUED
  -> INGESTING
  -> PARSING
  -> INDEXING
  -> ANALYZING
  -> COMPILING
  -> VALIDATING
  -> PACKAGING
  -> READY
```

Terminal alternatives:

```text
FAILED
CANCELLED
```

State transitions are monotonic for a Build. A completed build is immutable.

### 17.1 Stage behavior

- `INGESTING`: bind exact source versions and ensure artifacts are available.
- `PARSING`: produce canonical snapshot.
- `INDEXING`: parse docs/embed/index and record generation.
- `ANALYZING`: run semantic enrichment.
- `COMPILING`: generate manifest.
- `VALIDATING`: deterministic + semantic + protocol validation.
- `PACKAGING`: create exportable artifact, hashes, metadata.
- `READY`: deployable.

If no supplemental docs exist, `INDEXING` records a completed empty/limited generation rather than bypassing state consistency.

### 17.2 Idempotency

Each stage has a durable stage key based on `build_id`. Re-running a stage after worker failure must either reuse validated immutable output or safely replace incomplete stage output associated only with that build. Every ownership-sensitive transition and result publication also verifies the exact live admission token. The heartbeat tracks the last database-confirmed lease as a monotonic deadline and stops external work after it can no longer prove ownership.

---

## 18. Build diff/review/rebuild design

A manual `review` means: create a new build using current source versions, rerun semantic review/enrichment and validation even if source hashes are unchanged.

A `rebuild` means: create a new build and reconstruct canonical/manifest/artifact using current source versions and current approved compiler/prompt/runtime configuration.

Source-change builds compute a diff against the previous ready build.

Diff output:

```python
class BuildDiff(BaseModel):
    added_operations: list[str]
    removed_operations: list[str]
    changed_operations: list[OperationChange]
    unchanged_operations: list[str]
    changed_schemas: list[str]
    changed_security: list[str]
    changed_documents: list[UUID]
```

Unchanged operations may reuse semantic enrichment by content hash; executable compilation still runs against the current canonical snapshot.

---

## 19. Generic MCP runtime design

### 19.1 Process startup

Runtime startup order:

1. load environment/config paths;
2. load manifest bytes;
3. verify manifest hash if configured;
4. validate `mcp-manifest/v1` schema;
5. verify runtime compatibility range;
6. load secret bundle from read-only secret path;
7. validate required credential profile references without logging values;
8. build in-memory tool/resource registry;
9. construct upstream host allowlist;
10. initialize `ApiClient`/auth providers;
11. initialize official MCP server and Streamable HTTP app;
12. report readiness only after all prior steps pass.

### 19.2 Low-level MCP server

The implementation must publish schemas from manifest data. It shall use the official SDK layer that permits exact schema control rather than generating Python functions from the source API.

Handlers:

- list tools from registry;
- call tool via generic executor;
- list/read resources where manifest contains resources;
- health outside MCP via ASGI route or sidecar app route.

### 19.3 Runtime modules

```text
mcp_runtime/app/
├── main.py
├── core/config.py
├── manifest/
│   ├── models.py
│   ├── loader.py
│   └── schema.py
├── server/
│   ├── mcp_server.py
│   ├── tool_registry.py
│   └── resource_registry.py
├── executor/
│   ├── tool_executor.py
│   ├── request_builder.py
│   ├── response_mapper.py
│   └── errors.py
├── clients/
│   └── api_client.py
├── auth/
│   ├── upstream.py
│   ├── bearer.py
│   ├── api_key.py
│   ├── basic.py
│   ├── oauth_client_credentials.py
│   └── inbound.py
├── security/
│   ├── allowlist.py
│   ├── url_policy.py
│   └── redaction.py
├── validation/
│   └── arguments.py
└── observability/
    └── logging.py
```

### 19.4 Request builder

Input: validated tool args + manifest request mapping.

Output: immutable `UpstreamRequest`:

```python
class UpstreamRequest(BaseModel):
    method: HttpMethod
    url: AnyHttpUrl
    headers: dict[str, str]
    query: list[tuple[str, str]]
    json_body: JsonValue | None
    form_body: dict[str, str] | None
    timeout_ms: int
```

Caller arguments never override scheme/host/auth headers.

### 19.5 API client

`ApiClient` wraps a shared `httpx.AsyncClient` configured with:

- bounded connection pool;
- connect/read/write/pool timeouts;
- no automatic redirects unless policy wrapper approves each target;
- max response size enforcement via streaming;
- TLS verification enabled by default;
- proxy behavior explicitly configured, not inherited unexpectedly in hardened deployments;
- normalized exceptions.

### 19.6 Upstream auth

Auth providers receive secret material and modify the request in a controlled layer after user argument mapping.

OAuth client-credentials provider caches access tokens in runtime memory until near expiry; tokens are never persisted/logged.

### 19.7 Runtime result mapping

Success:

- preserve status metadata in structured `_meta` where appropriate;
- return structured content for JSON;
- return bounded text for text;
- redact configured sensitive fields when a project policy marks them secret.

Failure categories:

- invalid caller arguments;
- authentication failure to MCP runtime;
- upstream auth failure;
- upstream 4xx;
- upstream 5xx;
- timeout;
- connection failure;
- response too large;
- unsupported content type;
- policy/allowlist block;
- internal manifest/runtime error.

Errors returned to the MCP caller must be useful but must not include secrets, stack traces, internal file paths, Docker details, or decrypted credentials.

---

## 20. Inbound MCP authentication design

### 20.1 Static bearer mode

Default production mode.

Control plane generates at least 256 bits of random token entropy. Stored record contains only a slow/secure hash or HMAC verifier and a non-secret display prefix.

The runtime secret bundle contains verifier material sufficient to validate tokens but not expose them through the manifest.

Rotation can support a short overlap window with old + new verifier entries, then old token revocation.

### 20.2 External OAuth/OIDC verifier mode

Optional provider mode where runtime validates access tokens from an administrator-configured external issuer using issuer metadata/JWKS/audience/scope rules. The runtime acts as a resource server; the platform does not need to become a full identity provider.

This mode must integrate through the MCP SDK's supported authorization hooks when compatible with the pinned SDK.

### 20.3 Development unauthenticated mode

May be enabled only when:

- installation explicitly sets development mode; and
- project configuration marks inbound auth disabled.

The UI must display a warning and production docs must forbid it for internet-exposed endpoints.

---

## 21. Secret management

### 21.1 Control-plane encryption

Secret payloads are encrypted using authenticated encryption (AES-256-GCM through the approved cryptography library) with a master key supplied outside the database.

Requirements:

- 32-byte master key minimum;
- versioned key identifier;
- fresh nonce per encryption;
- authenticated associated data includes project ID + credential ID + credential scheme;
- ciphertext stored in PostgreSQL;
- master key never stored in PostgreSQL;
- key rotation is supported through `key_version` and a re-encryption operation.

The configured cipher is a versioned key ring: only the active version encrypts, prior configured
versions decrypt, unknown versions fail closed, and the re-encryption CLI/service locks and rewrites
records transactionally before an old key is removed.

### 21.2 Runtime secret materialization

The deployment worker decrypts only the credentials required for the selected build, writes a project-specific secret bundle to a host path/volume with restrictive ownership/permissions, and mounts it read-only into the runtime.

Secrets are not passed through:

- Docker labels;
- manifest JSON;
- command-line arguments;
- export bundles;
- application logs.

### 21.3 Secret deletion/revocation

Revoking a credential prevents new deployments using it and triggers active runtime replacement/stop when required for security. Plain secret recovery is never offered through the UI.

---

## 22. Deployment state machine

Statuses:

```text
PENDING
 -> DEPLOYING
 -> HEALTHCHECK
 -> RUNNING
```

Alternatives:

```text
UNHEALTHY
STOPPING -> STOPPED
FAILED
```

A rollback creates a new Deployment row with `rollback` intent referencing a previous READY Build; historical deployment
rows are immutable except operational status timestamps. Eligibility requires a non-active target
whose `activated_at` evidence is complete and whose activation proof recomputes against the exact
project, build, deployment, container, image, hostname, manifest, runtime version, and verification
time. A deployment stopped or failed before activation is ineligible regardless of its status
history. The same domain predicate drives the rollback transaction and `DeploymentRead` capability.

### 22.1 Deploy algorithm

1. assert Build `READY`;
2. acquire project deployment lock;
3. verify project hostname uniqueness;
4. materialize manifest + secret bundle;
5. create project network if missing;
6. create replacement container using pinned runtime image/digest;
7. attach network and Traefik labels;
8. start container;
9. poll container readiness, then probe the Traefik edge route with the expected
   immutable Build ID and Deployment ID;
10. if healthy, persist a content-bound activation proof, make the replacement
    authoritative, and commit it `RUNNING` before destructive superseded cleanup;
11. if unhealthy, remove replacement and keep old healthy deployment intact;
12. persist final state/audit event;
13. release lock.

During step 10 the candidate moves through durable `verified` and
`retiring_previous` activation phases. Each verification is bound to the exact project,
Build, Deployment, container ID, image digest, hostname, manifest digest, runtime
version, and verification timestamp. The candidate becomes `RUNNING` in the same
transaction that records its final activation phase, before destructive cleanup of the
superseded runtime. A cleanup retry must re-inspect the exact candidate identity and
probe `/readyz` through the edge again. If that proof fails, the invalid candidate is
stopped and marked unhealthy; the predecessor is restored only after its exact runtime
and edge identity are healthy again.

Never stop the currently healthy container before a replacement passes readiness unless Docker resource constraints make zero-downtime impossible and the user explicitly requested a stop-first deployment. A stop-first transition excludes only the STOPPING rows created by that same locked transition; unrelated in-progress deployments remain conflicts, and the durable DEPLOY command cannot overtake its STOP predecessor.

Container readiness alone is insufficient for replacement. The edge probe must reach
the candidate through its project hostname/network and receive `/readyz` evidence for
the exact candidate Build and Deployment. This prevents Docker-provider propagation
delay, or an older same-Build runtime, from being mistaken for the replacement.
An activation proof is operational evidence, not a substitute for the live edge probe;
every resumed activation or cleanup retry obtains a fresh proof before retiring another
runtime.

Authentication-only maintenance uses `security_refresh` intent and the exact active immutable
Build. It may bypass only unrelated pending source/routing drift; artifact integrity, ownership,
runtime compatibility, and current secret material remain mandatory. Revoking the last valid
inbound verifier commits the revocation with a durable STOP and creates no invalid replacement.

---

## 23. Docker naming and labels

Stable resource names use UUID fragments, not user-controlled strings alone.

Example:

```text
container: mcp-<slug>-<project-id-8>-<deployment-id-8>
network:   mcp-net-<project-id-8>
router:    mcp-<project-id-8>
service:   mcp-<project-id-8>
```

Required labels include only non-sensitive routing metadata:

```text
traefik.enable=true
traefik.http.routers.<router>.rule=Host(`<project-hostname>`)
traefik.http.routers.<router>.entrypoints=websecure
traefik.http.routers.<router>.tls=true
traefik.http.services.<service>.loadbalancer.server.port=<runtime-port>
```

No secret in labels.

---

## 24. REST API design

All responses use a stable error envelope on failure:

```json
{
    "error": {
        "code": "PROJECT_NOT_FOUND",
        "message": "Project was not found.",
        "details": {},
        "request_id": "..."
    }
}
```

Management collections use a common bounded page contract (`items`, `total`, `page`, `page_size`)
with stable ordering. The browser explicitly fetches every page only for workflows that require a
complete set; repositories never return all retained users/projects/credentials/tokens/AI runs in
one unbounded query.

### 24.1 Auth/users

```text
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
POST   /api/v1/auth/logout
GET    /api/v1/auth/me
GET    /api/v1/users                 ADMIN
POST   /api/v1/users                 ADMIN
PATCH  /api/v1/users/{id}            ADMIN
```

### 24.2 Projects

```text
GET    /api/v1/projects
POST   /api/v1/projects
GET    /api/v1/projects/{project_id}
PATCH  /api/v1/projects/{project_id}
DELETE /api/v1/projects/{project_id}
```

Project deletion is blocked while an active deployment or nonterminal Build exists. Before relational cascade, the transaction persists a durable cleanup job containing every reachable source blob, manifest, export, chunk manifest, and exact vector generation. The API returns `202` with that job; admin cleanup endpoints expose counts, retry state, bounded errors, and terminal outcome. External workers use expiring leases and live reference checks, so retries are idempotent and content shared by another surviving row is never removed.

Retention is enforced, not decorative: Build retention preserves the newest configured count and every active, deployed, or nonterminal Build; source retention preserves each Source's latest version, the exact cutoff boundary, and every version referenced by a retained Build. Candidate rows and cleanup targets are committed atomically. Source upload staging additionally arms a durable delayed orphan guard before final object commit, closing the storage-before-database failure window.

### 24.3 Sources

```text
GET    /api/v1/projects/{id}/sources
POST   /api/v1/projects/{id}/sources
POST   /api/v1/projects/{id}/sources/{source_id}/versions
POST   /api/v1/projects/{id}/sources/{source_id}/refresh
GET    /api/v1/projects/{id}/sources/{source_id}/versions
GET    /api/v1/source-versions/{version_id}/metadata
```

Each returned source issue includes `source_version_id`, `stage`, `code`, `severity`, `message`,
optional `pointer`/`line`/`column`, and redacted `details`. Build error fields are aggregate status
only and are not a per-source attribution contract.

### 24.4 Credentials

```text
GET    /api/v1/projects/{id}/credentials
POST   /api/v1/projects/{id}/credentials
POST   /api/v1/projects/{id}/credentials/{credential_id}/rotate
DELETE /api/v1/projects/{id}/credentials/{credential_id}
```

Secret responses return metadata only after creation/rotation. Rotation replaces the encrypted
secret while preserving the credential's immutable security-scheme binding; a supplied metadata
change is rejected without mutation. Remapping uses a replacement credential and new Build.

### 24.5 Builds

```text
GET    /api/v1/projects/{id}/builds
POST   /api/v1/projects/{id}/builds
GET    /api/v1/builds/{build_id}
POST   /api/v1/builds/{build_id}/cancel
POST   /api/v1/projects/{id}/review
POST   /api/v1/projects/{id}/rebuild
GET    /api/v1/builds/{build_id}/events        SSE
GET    /api/v1/builds/{build_id}/diff
GET    /api/v1/builds/{build_id}/manifest
GET    /api/v1/builds/{build_id}/validation
GET    /api/v1/builds/{build_id}/export
```

`POST /builds` binds the current source versions and returns `202 Accepted` with build resource.

### 24.6 Operation exclusions

```text
GET    /api/v1/builds/{build_id}/operations
POST   /api/v1/projects/{id}/operation-exclusions
DELETE /api/v1/projects/{id}/operation-exclusions/{exclusion_id}
```

Persistent exclusion rules should bind to stable operation keys and be carried into new builds while the operation still exists.

### 24.7 Deployments

```text
GET    /api/v1/projects/{id}/deployments
POST   /api/v1/projects/{id}/deployments
GET    /api/v1/deployments/{deployment_id}
POST   /api/v1/deployments/{deployment_id}/stop
POST   /api/v1/deployments/{deployment_id}/restart
POST   /api/v1/projects/{id}/rollback
GET    /api/v1/deployments/{deployment_id}/events    SSE
```

### 24.8 MCP access

```text
GET    /api/v1/projects/{id}/mcp-access
POST   /api/v1/projects/{id}/mcp-access/tokens
POST   /api/v1/projects/{id}/mcp-access/tokens/{token_id}/rotate
DELETE /api/v1/projects/{id}/mcp-access/tokens/{token_id}
PUT    /api/v1/projects/{id}/mcp-access/auth-mode
```

### 24.9 Settings/system

```text
GET    /api/v1/settings
PUT    /api/v1/settings/models             ADMIN
PUT    /api/v1/settings/openrouter         ADMIN
GET    /api/v1/settings/models/catalog     ADMIN
POST   /api/v1/settings/openrouter/test    ADMIN
GET    /api/v1/audit                       ADMIN
GET    /api/v1/health
GET    /api/v1/ready
```

The OpenRouter test may perform a provider metadata/capability check; it does not invoke a company product API.

---

## 25. Frontend design

### 25.1 Routing

```text
/login
/
/projects
/projects/new
/projects/:projectId
/projects/:projectId/sources
/projects/:projectId/tools
/projects/:projectId/documentation
/projects/:projectId/builds
/projects/:projectId/builds/:buildId
/projects/:projectId/validation/:buildId
/projects/:projectId/deployment
/projects/:projectId/credentials
/projects/:projectId/settings
/builds
/deployments
/activity
/settings
/settings/providers
/settings/models
/settings/users
```

### 25.2 Project creation wizard

Steps:

1. Project identity/name/slug.
2. Executable API source: OpenAPI upload/URL or API Inventory upload/URL.
3. Supplemental documentation.
4. Source server/base URL selection/configuration.
5. Upstream authentication mapping/credential entry.
6. Analyze/build request.
7. Build progress.
8. Validation/coverage review.
9. MCP access configuration.
10. Deploy.

The wizard may be exited/resumed after project creation; durable state lives in backend.

### 25.3 Project detail tabs

- Overview
- Sources
- Operations/Tools
- Documentation
- Builds
- Validation
- Deployment
- Credentials
- Settings

### 25.4 Build progress UI

Display deterministic stage statuses, counts, warnings, and errors. Do not expose raw AI chain-of-thought. AI-related UI can show model, stage, usage/cost metadata, and validated findings.

### 25.5 Validation UI

Must display:

- source operation count;
- exclusions;
- expected tools;
- generated tools;
- coverage percentage;
- blocking errors;
- warnings;
- per-operation mapping/provenance;
- diff from prior build when applicable.

### 25.6 Deployment UI

Must display:

- endpoint URL;
- runtime/build versions;
- health;
- auth mode;
- access token metadata;
- deployment history;
- stop/restart/rollback controls subject to permissions.

No chat page exists.

---

## 26. Error taxonomy

All internal exceptions map to stable categories.

### Domain errors

- `NotFoundError`
- `ConflictError`
- `InvalidStateError`
- `PermissionDeniedError`
- `ValidationFailedError`

### Client errors

- `ClientConnectionError`
- `ClientTimeoutError`
- `ClientAuthenticationError`
- `ClientRateLimitError`
- `ClientResponseError`
- `ClientUnavailableError`

### Build errors

- `SourceParseError`
- `ReferenceResolutionError`
- `CanonicalizationError`
- `IndexingError`
- `AIAnalysisError`
- `CompilationError`
- `CoverageValidationError`
- `ManifestValidationError`
- `ProtocolValidationError`
- `PackagingError`

### Deployment errors

- `DockerOperationError`
- `RuntimeStartupError`
- `RuntimeHealthError`
- `HostnameConflictError`
- `SecretMaterializationError`

Error messages persisted to DB must be sanitized.

---

## 27. Retry policy

Retry only transient failures.

Retryable examples:

- HTTP 429/selected 5xx from OpenRouter;
- connection reset/timeouts;
- transient Milvus/Redis connection errors;
- Docker daemon temporary failures;
- remote source fetch 5xx.

Non-retryable examples:

- invalid credentials after confirmed 401/403;
- invalid OpenAPI;
- invalid structured AI response after schema retry limit;
- deterministic compiler error;
- duplicate hostname;
- unsupported media type;
- security policy block.

Use bounded exponential backoff with jitter and explicit attempt counts. Jobs must record attempt/failure category. Redis connections and blocking queue operations have explicit socket deadlines. A remote source fetch owns one total deadline across DNS/policy resolution, redirects, retries, and streamed body reads; OpenRouter bodies are streamed through a byte cap before decode.

---

## 28. Concurrency and locking

Required locks:

- one active build creation transaction per project snapshot decision;
- one deployment mutation at a time per project;
- source refresh lock per source;
- secret rotation lock per credential/token.
- parent-job then cleanup-target locks for cleanup state;
- one PostgreSQL advisory project lock around runtime Docker effects.

Use PostgreSQL transaction/advisory locking where correctness is durable; Redis locks may optimize distributed coordination but must not be the sole correctness mechanism for destructive state.
All reclaimable work uses a new execution token. A stale Build, runtime command, or cleanup worker
cannot publish terminal state for its successor even if an earlier external call returns late.

---

## 29. Logging, metrics, audit

### 29.1 Structured logging

JSON logs in production. Common fields:

- timestamp
- level
- service/component
- request_id/job_id
- actor_id when appropriate
- project_id
- build_id
- deployment_id
- error_code

The formatter emits only an allowlisted JSON-safe context, including safe cleanup target/job,
runtime command, admission-attempt, and retry fields. Raw exception text and arbitrary log messages
are not production fields; exception type chains and query-stripped routes provide bounded
diagnostics without echoing credentials.

### 29.2 Metrics

Expose Prometheus-compatible metrics endpoint or library integration for:

Builder:

- request counts/latency;
- job counts/durations/failures;
- OpenRouter request latency/rate-limit/error counts and usage/cost totals;
- Milvus operation latency/errors;
- build stage duration;
- generated operation count;
- deployment success/failure.

Runtime:

- MCP requests;
- tool-call count/latency;
- upstream API status classes;
- timeouts;
- auth failures;
- blocked upstream destinations;
- response-size rejections.

Metrics labels must avoid high-cardinality secret/user-controlled values.

### 29.3 Audit events

Audit, at minimum:

- login/security administration changes;
- user creation/role/disable;
- project create/update/delete;
- source create/version/refresh;
- credential create/rotate/revoke;
- MCP token create/rotate/revoke;
- build/review/rebuild/cancel;
- operation exclusion changes;
- deployment/restart/stop/rollback;
- OpenRouter/model setting changes.

---

## 30. Security requirements

### 30.1 Input security

- strict upload size limits;
- YAML parser configured for safe loading only;
- no object constructors;
- no archive extraction in core V1;
- JSON depth/size safeguards;
- `$ref` recursion limits;
- HTML sanitization before rendering documentation in browser;
- PDFs processed in isolated/bounded worker context where possible;
- filenames never used directly as filesystem paths.

### 30.2 Web security

- HTTPS expected in production;
- secure cookies;
- CSRF protection;
- CSP and standard security headers;
- explicit CORS allowlist; default same-origin deployment;
- password rate limiting;
- login audit;
- no public sign-up.

### 30.3 SSRF

Both source fetcher and runtime upstream requester use shared policy semantics. Internal/private target APIs must be intentionally allowlisted in project/system configuration; unrestricted RFC1918 access is not implicitly enabled solely because the application is self-hosted.

### 30.4 Dependency/runtime security

- lock dependencies;
- run vulnerability scans in CI;
- minimal container images;
- runtime non-root/read-only;
- no secrets in image layers;
- SBOM produced for releases;
- container images signed when release infrastructure is configured.

---

## 31. Test design

### 31.1 Backend unit tests

Mock interfaces, not third-party SDK internals where avoidable.

Must cover:

- service state rules;
- repositories;
- canonicalization;
- tool naming;
- request mapping;
- coverage calculations;
- encryption/redaction;
- auth/permissions;
- diff logic.

### 31.2 Parser fixture tests

Fixtures include:

- OpenAPI 3.0 JSON/YAML;
- OpenAPI 3.1 JSON/YAML;
- nested/circular `$ref`;
- multiple servers;
- each supported auth scheme;
- path/query/header/body combinations;
- enums/nullable/oneOf/anyOf/allOf representative cases;
- multipart/form;
- malformed/unsupported cases.

Golden canonical snapshots detect accidental semantic changes.

### 31.3 Compiler golden tests

Canonical fixtures compile to deterministic manifest snapshots. The same input must hash identically across repeated runs with same compiler/version.

### 31.4 AI provider contract tests

Use recorded/fake structured responses for deterministic CI. Live OpenRouter tests are opt-in/integration-only and never required for ordinary PR unit suites.

Validate:

- schema enforcement;
- invalid response handling;
- retry/rate-limit mapping;
- embeddings dimension handling;
- model capability filtering.

### 31.5 Milvus integration tests

Run against test Milvus in integration CI profile. Verify project/generation filters prevent cross-project retrieval.

### 31.6 Runtime tests

A mock upstream HTTP API fixture is mandatory.

Tests must verify:

- tools/list exact schemas;
- correct path/query/body mapping;
- credential injection;
- caller cannot override upstream host/auth;
- URL/SSRF blocks;
- response mapping;
- auth token behavior;
- timeout/size failures;
- two different manifests on same runtime image.

### 31.7 MCP protocol tests

Use the official MCP client and MCP Inspector-compatible flow against a running runtime container.

### 31.8 Deployment integration tests

Docker-enabled test profile creates two projects/runtimes, verifies independent routes/networks/health, performs replacement and rollback, then cleans resources.

### 31.9 Frontend tests

- component/feature tests with Vitest/Testing Library;
- API mocking for normal tests;
- Playwright E2E for import -> build -> validation -> deploy flow using fixture services.

### 31.10 Security tests

Automated tests for:

- malicious URL/redirect/DNS cases;
- path traversal;
- header injection;
- secret redaction;
- authz bypass;
- oversized payloads;
- invalid YAML tags;
- HTML XSS content;
- tool args attempting host override.

---

## 32. Compatibility/versioning

Version independently:

- REST API (`/api/v1`);
- canonical model (`canonical-api/v1`);
- API Inventory (`api-inventory/v1`);
- MCP manifest (`mcp-manifest/v1`);
- compiler semantic version;
- generic runtime semantic version.

A build stores all relevant versions. Runtime startup rejects manifests outside its declared compatibility range.

Migrations between manifest schema versions are builder responsibilities; active old builds remain deployable only while a compatible runtime image remains available.

---

## 33. Design completion criteria

The design is fully implemented when:

1. Every external integration has the required client boundary and no forbidden direct SDK usage remains outside clients/providers.
2. All authoritative tables/state machines exist through Alembic migrations and are covered by repository tests.
3. OpenAPI/API Inventory -> canonical -> manifest is typed, versioned, deterministic, and provenance-preserving.
4. AI enrichment is structured and cannot mutate executable fields.
5. Milvus indexing is project/build isolated and rebuildable.
6. Builds are immutable, auditable, diffable, and retry-safe.
7. Validation reports prove 100% expected operation coverage or explicit exclusions.
8. Generic MCP runtime serves exact generated schemas and deterministically maps calls to allowed upstream requests.
9. MCP inbound auth and upstream API auth are independent and secrets are never exposed in manifests/exports/logs.
10. Deployment worker is the only Docker-authoritative process and replacement/rollback behavior is tested.
11. The documented REST endpoints and frontend workflows exist without chat/HITL/subscription features.
12. Unit, integration, protocol, E2E, and security suites cover the specified boundaries.
