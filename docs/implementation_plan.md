# MCPlica Implementation Plan

**Status:** Authoritative AI-executable implementation roadmap  
**Date:** 2026-08-24  
**Execution mode:** Incremental, direct implementation against the live repository

## 1. Document ownership

This document owns the **implementation sequence**: phases, tasks, dependencies, target locations, migrations, integration steps, verification, milestones, and objective completion criteria.

It does not redefine product scope, architecture, technical contracts, technology standards, or governance. Those are authoritative in:

- `product_requirements.md`
- `architecture.md`
- `design_document.md`
- `tech_stack.md`
- `open_source_and_sponsorship_model.md`

If this plan references a design that conflicts with an owner document, implement the owner document and update this plan accordingly.

---

## 2. Instructions to the coding agent

The coding agent shall treat the six-document set as a single implementation contract.

### Mandatory execution rules

1. Implement incrementally in the phase order below unless a dependency requires a small prerequisite adjustment.
2. Work directly in the canonical codebase. Do not create V2/shadow/canary/parallel implementations of the same subsystem.
3. Do not reinterpret the product as SaaS, multi-tenant, chat, or an AI agent platform.
4. Do not add chat/conversation/agent-loop/HITL/subscription/billing/entitlement features.
5. Do not use pgvector; Milvus is the vector database.
6. Do not generate a separate maintained Python MCP server codebase for each Project. Build one generic runtime and project-specific manifests/artifacts.
7. OpenRouter is build/review/indexing intelligence only; never use it in MCP runtime execution.
8. Use explicit clients for every infrastructure/external component as required by the architecture.
9. Do not allow services/routers to bypass clients/providers/repositories.
10. Keep executable API mappings deterministic and source-derived. AI output may enrich semantic fields only.
11. Every phase must finish with tests, documentation updates, migrations where needed, and an objective phase gate before continuing.
12. No TODO/pass/mock implementation may count as completion. Mocks are allowed only in tests.
13. No temporary production paths, duplicated runtimes, hidden feature flags, or stub endpoints may remain at final completion.
14. Preserve security boundaries from the first implementation; do not postpone secret protection, SSRF rules, or Docker authority separation to a cosmetic hardening phase if an earlier feature depends on them.
15. Use database migrations for every schema change; do not rely on automatic table creation.
16. Every new external dependency must satisfy `tech_stack.md` dependency rules and be locked.
17. Keep the documentation set updated when implementation reveals a necessary clarification; do not silently deviate.

---

## 3. Target repository structure

Create/normalize this structure early and keep all subsequent implementation inside it:

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
├── mcp_runtime/
│   ├── app/
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   ├── tests/
│   └── package.json
├── packages/
│   └── contracts/
│       ├── src/mcp_contracts/
│       ├── tests/
│       └── pyproject.toml
├── migrations/alembic/
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
├── architecture.md
├── design_document.md
├── product_requirements.md
├── implementation_plan.md
├── tech_stack.md
└── open_source_and_sponsorship_model.md
```

Do not create a microservice-per-module directory structure.

---

# Phase 0 — Repository foundation and engineering baseline

## Objective

Create a reproducible monorepo foundation, dependency locking, local development environment, CI skeleton, application factories, and shared standards before domain implementation.

## Dependencies

None.

## Tasks

### 0.1 Python workspace

Create:

- root `pyproject.toml` as uv workspace configuration;
- `backend/pyproject.toml`;
- `mcp_runtime/pyproject.toml`;
- `packages/contracts/pyproject.toml` as an infrastructure-free shared contract package;
- root `uv.lock`.

Configure:

- Python 3.13;
- Ruff lint/format;
- mypy or Pyright according to `tech_stack.md` (use the selected standard consistently);
- pytest;
- coverage;
- import boundaries if a suitable lightweight rule tool is selected.

### 0.2 Frontend workspace

Create React + TypeScript + Vite app in `frontend/`.

Configure:

- Tailwind CSS;
- shadcn/ui;
- React Router;
- TanStack Query;
- React Hook Form + Zod;
- ESLint;
- Prettier if retained by the chosen toolchain;
- Vitest + Testing Library.

### 0.3 FastAPI skeleton

Create:

- `backend/app/main.py` application factory;
- `backend/app/core/config.py` using Pydantic Settings;
- `backend/app/core/logging.py`;
- `backend/app/core/exceptions.py`;
- versioned router root `backend/app/api/router.py`;
- `/api/v1/health` and `/api/v1/ready`.

### 0.4 Runtime skeleton

Create minimal `mcp_runtime/app/main.py`, config, logging, health route, and Dockerfile. Do not yet implement generated tools.

### 0.5 Base Compose

Create `infra/compose.yaml` containing:

- frontend;
- api;
- worker service using the same backend image/codebase with the real RQ worker command; it may have no registered product jobs until later phases but must boot and connect successfully;
- PostgreSQL;
- Redis;
- Milvus standalone plus its officially required supporting services for the pinned Milvus release;
- Traefik.

Do not enumerate dynamic project MCP containers.

Configure separate networks:

- builder internal network;
- edge network for frontend/API as required;
- do not attach Milvus/Postgres/Redis to public edge.

### 0.6 CI skeleton

Add GitHub Actions workflows for:

- backend lint/type/unit tests;
- runtime lint/type/unit tests;
- frontend lint/type/unit tests;
- dependency/security scan baseline;
- Docker build smoke tests.

### 0.7 Developer commands

Provide root scripts/Makefile/task runner commands for:

- install;
- lint;
- format;
- typecheck;
- unit tests;
- integration profile;
- compose up/down;
- migrations;
- frontend dev/build.

## Verification

- clean clone installs from lockfiles;
- backend and frontend boot;
- base Compose starts all infrastructure healthy;
- `/health` responds;
- CI runs on an empty/minimal domain skeleton;
- no chat/billing/multi-tenant modules exist.

## Phase gate

Phase 0 is complete only when local and CI environments are reproducible and the base service topology matches `architecture.md`.

---

# Phase 1 — Core clients, database foundation, security primitives, local auth

## Objective

Implement the mandatory client architecture and durable base models before feature services use infrastructure.

## Dependencies

Phase 0.

## Tasks

### 1.1 Client base contracts

Create:

```text
backend/app/clients/base/client.py
backend/app/clients/base/exceptions.py
backend/app/clients/base/retry.py
backend/app/clients/base/health.py
```

Define project-owned exception taxonomy and lifecycle protocols.

### 1.2 Database client

Create `backend/app/clients/database/postgres_client.py`.

Responsibilities only:

- SQLAlchemy async engine;
- session factory;
- transaction context;
- pool configuration;
- health check;
- shutdown.

No project/domain queries.

### 1.3 Redis client

Create `backend/app/clients/cache/redis_client.py`.

Expose typed wrappers needed for:

- get/set/delete/expire;
- publish;
- lightweight locks/idempotency support;
- health/lifecycle.

Do not put domain build logic in the client.

### 1.4 HTTP client

Create `backend/app/clients/http/http_client.py`.

Implement:

- shared async connection pooling;
- explicit timeouts;
- bounded fetch support;
- redirect hooks;
- standardized errors;
- request correlation;
- no logging of auth headers/bodies by default.

SSRF policy is added in Phase 3 before remote fetch is enabled.

### 1.5 Milvus client

Create `backend/app/clients/vector/milvus_client.py` with connection/collection/insert/search/delete/health operations.

Add `backend/app/providers/vector/base.py` and `milvus.py`.

### 1.6 OpenRouter client/provider

Create:

```text
backend/app/clients/ai/openrouter_client.py
backend/app/providers/ai/base.py
backend/app/providers/ai/openrouter.py
```

Client owns HTTP/API details. Provider owns model selection, structured generation, embeddings, capability/model catalog normalization.

Do not create MCP/runtime calls here.

### 1.7 Storage client/provider

Create filesystem artifact storage:

```text
backend/app/clients/storage/filesystem_client.py
backend/app/providers/storage/base.py
backend/app/providers/storage/filesystem.py
```

Use content-addressed immutable paths and atomic writes.

### 1.8 Docker client

Create `backend/app/clients/docker/docker_client.py`, but ensure dependency construction is available only to the deployment worker profile.

Methods required eventually:

- image inspect/pull;
- network create/inspect/delete/connect/disconnect;
- container create/start/stop/remove/inspect;
- health/status inspect;
- safe label/env/mount configuration.

### 1.9 MCP validation client

Create `backend/app/clients/mcp/mcp_client.py` wrapping the official MCP Python client for protocol validation against test/running runtimes.

### 1.10 Encryption/redaction

Create:

```text
backend/app/core/encryption.py
backend/app/core/redaction.py
backend/app/core/security.py
```

Implement versioned AES-256-GCM secret envelope exactly as `design_document.md` specifies.

### 1.11 Initial database migrations

Initialize Alembic at `migrations/alembic/` using the backend model metadata.

Migration 0001 creates:

- `users`;
- `auth_sessions`;
- `system_settings`;
- `audit_events`.

### 1.12 Local authentication

Implement:

```text
backend/app/services/auth/
backend/app/services/users/
backend/app/repositories/users.py
backend/app/repositories/auth_sessions.py
backend/app/api/auth.py
backend/app/api/users.py
```

Implement Admin/Builder roles, no public registration, bootstrap-first-admin CLI/script, secure cookie/session flow, CSRF protection, session revocation, password hashing.

### 1.13 Frontend login shell

Implement:

- login page;
- authenticated route guard;
- current-user state;
- app shell/sidebar with Dashboard, Projects, Builds, Deployments, Activity, Settings;
- no chat navigation.

## Tests

- client unit tests with SDK/transport fakes;
- database transaction tests;
- Redis/Milvus health integration tests under integration profile;
- encryption round-trip/tamper/AAD/key-version tests;
- secret redaction tests;
- auth/session/CSRF/permission tests;
- Docker client never instantiated in normal API process test/config assertion.

## Phase gate

All later code can access infrastructure only through these clients/providers/repositories. A static grep/import-boundary check should fail CI if forbidden direct SDK usage is introduced outside approved integration modules.

---

# Phase 2 — Project, source, credential, and audit domain

## Objective

Implement durable project management and immutable source/secret foundations.

## Dependencies

Phase 1.

## Tasks

### 2.1 Database migration 0002

Create:

- `projects` without `active_build_id`/`active_deployment_id` foreign keys yet because their target tables do not exist;
- `project_sources`;
- `source_versions`;
- `project_credentials`;
- necessary indexes/constraints.

Migration 0007 adds the final active Build/Deployment references after those tables exist.

### 2.2 Domain models

Create:

```text
backend/app/domain/projects/
backend/app/domain/sources/
backend/app/domain/credentials/
```

Include enums/value objects for project slug, source type, source origin, credential purpose/type.

### 2.3 Repositories

Create:

- `ProjectRepository`;
- `SourceRepository`;
- `CredentialRepository`;
- extend `AuditRepository`.

### 2.4 ProjectService

Location: `backend/app/services/projects/`.

Implement:

- create/list/get/update;
- slug validation/uniqueness;
- hostname generation from `MCP_BASE_DOMAIN`;
- enable/disable;
- controlled deletion preconditions.

Do not implement parsing/build/deployment inside `ProjectService`.

### 2.5 SourceService

Location: `backend/app/services/sources/`.

Implement:

- source logical records;
- immutable version creation;
- upload streaming/hash/storage;
- source metadata;
- URL source registration, but remote fetching remains disabled until Phase 3 SSRF controls are present;
- deduplicate identical versions by hash.

### 2.6 CredentialService

Implement encrypted create/rotate/revoke metadata for:

- upstream API credentials;
- OAuth client credentials;
- later MCP verifier material.

Secret values may be accepted on create/rotate and must never be returned later.

### 2.7 REST APIs

Implement project/source/credential endpoints from `design_document.md`.

### 2.8 Frontend project foundation

Implement:

- project list;
- create/edit project;
- project detail shell/tabs;
- source list/upload;
- credential metadata/config forms;
- permission-aware controls.

## Tests

- slug/hostname rules;
- source immutability;
- hash deduplication;
- project deletion preconditions;
- secret never returned/logged;
- role authorization;
- audit event creation.

## Phase gate

A user can securely create a Project, attach immutable uploaded sources, and configure encrypted credentials without any compiler/runtime implementation yet.

---

# Phase 3 — Secure source fetch, OpenAPI/API Inventory parsing, canonical API model

## Objective

Create the deterministic executable source pipeline and canonical model that all generation depends on.

## Dependencies

Phases 1-2.

## Tasks

### 3.1 SSRF/url policy library

Create shared backend policy modules:

```text
backend/app/core/url_policy.py
backend/app/core/network_policy.py
```

Implement:

- scheme validation;
- hostname normalization;
- DNS resolution checks;
- IP range policy;
- redirect revalidation;
- max response bytes;
- timeout policy;
- blocked metadata/link-local/loopback rules with explicit controlled internal allowlist configuration.

Reuse equivalent rule definitions later in runtime rather than sharing a live service dependency.

### 3.2 Enable remote source refresh

Add secure remote fetch through `HttpClient` only.

Persist ETag/Last-Modified and immutable version when content changes.

### 3.3 Canonical domain models

Create:

```text
backend/app/domain/api/canonical.py
backend/app/domain/api/schema.py
backend/app/domain/api/provenance.py
```

Implement `canonical-api/v1` models from `design_document.md`.

### 3.4 API Inventory schema/parser

Create:

```text
backend/app/parsers/api_inventory/schema/api-inventory-v1.schema.json
backend/app/parsers/api_inventory/parser.py
backend/app/parsers/api_inventory/validator.py
```

Provide fixtures and user-facing format docs under `docs/api-inventory-v1.md`.

### 3.5 OpenAPI parser

Create:

```text
backend/app/parsers/openapi/parser.py
backend/app/parsers/openapi/references.py
backend/app/parsers/openapi/normalizer.py
backend/app/parsers/openapi/errors.py
```

Support 3.0.x/3.1.x JSON/YAML and rules from design.

### 3.6 Stable identifiers/tool-name seeds

Create pure deterministic utilities for:

- operation key;
- schema key;
- server key;
- stable name seed;
- provenance paths.

Golden-test them.

### 3.7 Migration 0003

Add:

- `canonical_snapshots`;
- any normalized build/source join prerequisites if appropriate.

### 3.8 Canonicalization service

Create `backend/app/services/importing/` and/or `services/canonicalization/` to select executable sources, resolve configuration, and persist immutable canonical snapshot.

### 3.9 Source validation UI

Add source parse preview showing:

- detected spec/version;
- servers;
- auth schemes;
- operation count;
- parse errors;
- schema/ref issues.

Do not yet claim MCP build completion.

## Tests

Must include the complete parser fixture matrix in `design_document.md` plus SSRF tests.

Golden snapshots verify equivalent input parses to stable canonical output.

## Phase gate

The system can ingest representative real OpenAPI/API Inventory sources and produce a complete, provenance-preserving canonical API snapshot without OpenRouter.

---

# Phase 4 — Documentation parsing, OpenRouter embeddings, and Milvus indexing

## Objective

Implement supplemental knowledge ingestion as a rebuildable semantic index without allowing it to define executable API operations.

## Dependencies

Phases 1-3.

## Tasks

### 4.1 Documentation parsers

Create:

```text
backend/app/parsers/documentation/markdown.py
backend/app/parsers/documentation/text.py
backend/app/parsers/documentation/html.py
backend/app/parsers/documentation/pdf.py
backend/app/parsers/documentation/models.py
backend/app/parsers/documentation/chunker.py
```

Requirements:

- safe bounded parsing;
- preserve headings/sections/source provenance;
- report image-only PDF as insufficient text; no OCR.

### 4.2 OpenRouter model configuration

Add encrypted/configured system OpenRouter secret and non-secret model selection settings.

Implement settings APIs/UI for:

- API key set/rotate/test;
- analysis model;
- validation model;
- embedding model;
- model catalog/capability filtering;
- build concurrency/context limits.

No hardcoded permanent model name dependency; selection is installation configuration from live OpenRouter catalog.

### 4.3 Embedding provider

Complete `OpenRouterProvider.embed()` with batching, rate limits, retries, usage metadata, dimension validation.

### 4.4 Milvus vector store

Create deterministic collection/index naming strategy and metadata schema from `design_document.md`.

Enforce project/generation filter in provider API so callers cannot accidentally execute an unscoped search.

### 4.5 Migration 0004

Create `document_index_generations` and metadata needed for chunk/index tracking.

### 4.6 IndexingService

Create `backend/app/services/indexing/`.

Pipeline:

- parse docs;
- normalize;
- chunk;
- calculate deterministic chunk IDs;
- embed;
- create/upsert generation;
- mark generation complete;
- record model/dimension/source fingerprint.

Failed new generations must not invalidate a previous usable generation.

### 4.7 Documentation UI

Display sources, parse status, indexed chunk count, model/dimension, generation status. Do not expose embeddings.

## Tests

- parser unit/security tests;
- chunk determinism;
- OpenRouter embedding fake/contract tests;
- Milvus integration tests including cross-project isolation;
- generation rebuild/delete behavior;
- no documentation-only executable operation creation.

## Phase gate

Given project docs, the system can build a project-scoped Milvus index and retrieve relevant chunks, while canonical executable API structure is unchanged.

---

# Phase 5 — AI semantic analysis, enrichment, prompt/version governance

## Objective

Use OpenRouter to improve MCP-facing semantics under strict typed boundaries.

## Dependencies

Phases 3-4.

## Tasks

### 5.1 Prompt bundle

Create versioned prompt files under:

```text
backend/app/prompts/analysis/
backend/app/prompts/enrichment/
backend/app/prompts/validation/
backend/app/prompts/manifest.py or registry.py
```

Every prompt has:

- stable ID;
- semantic version;
- explicit purpose;
- exact structured response schema ID;
- instructions forbidding executable invention;
- source-vs-retrieved context delimiters;
- no secrets.

### 5.2 AI result domain models

Create strict Pydantic models for:

- operation enrichment;
- terminology/categories;
- documentation correlation;
- relationship hints;
- semantic review findings.

### 5.3 Migration 0005 — Build core and AI-run audit

Create the build tables needed to make every AI analysis run belong to an immutable Build context:

- `builds`;
- `build_source_versions`;
- `build_ai_runs`.

At this phase the Build state machine/table includes all final statuses, even though compiler/validation stages are implemented in Phase 6. Analysis jobs must always run against a real Build ID bound to exact source versions. Do not create AI-run records without a Build FK.

### 5.4 Retrieval service

Create `backend/app/services/analysis/retrieval.py` to construct scoped retrieval queries and fetch bounded relevant chunks from `VectorStore`.

### 5.5 AnalysisService

Create `backend/app/services/analysis/service.py`.

For each operation/batch:

- collect deterministic source facts;
- retrieve relevant docs;
- call `AIProvider.structured_generate`;
- validate Pydantic result;
- enforce AI write-boundary allowlist;
- record model/prompt/context metadata;
- produce semantic-enrichment snapshot.

### 5.6 Cost/usage visibility

Persist provider-returned usage/cost metadata where available and aggregate by Build for the admin UI. This is operational visibility only.

### 5.7 Semantic review

Implement second-pass or validation-model review that reports contradictions such as a generated description claiming unsupported behavior. It may produce findings/corrections to semantic fields, never executable source mappings.

### 5.8 UI enrichment visibility

Operations screen differentiates:

- source summary/description;
- generated MCP title/description;
- documentation references;
- semantic warnings/confidence.

Do not show private model chain-of-thought.

## Tests

- structured output schema tests;
- malicious retrieved-doc prompt injection fixtures (AI instruction within docs must be treated as data, not system instruction);
- field write-boundary tests proving AI cannot change method/path/schema/security;
- retry/rate-limit/invalid output cases;
- deterministic fake-provider CI.

## Phase gate

AI can materially enrich semantics, but a test that injects an AI response attempting to change `GET /x` to `DELETE /y` is rejected and executable canonical data remains unchanged.

---

# Phase 6 — Build domain, deterministic MCP compiler, validation, artifacts

## Objective

Create immutable Builds and compile/validate `mcp-manifest/v1` artifacts.

## Dependencies

Phases 3-5.

## Tasks

### 6.1 Migration 0006 — Validation and exclusions

Build core tables already exist from Migration 0005. Create:

- `validation_reports`;
- `operation_exclusions`.

Add any compiler/packaging metadata columns that were intentionally reserved in the final `builds` model only through this migration if they could not exist in 0005; the preferred implementation is to create the complete final `builds` schema in 0005 so 0006 remains additive for validation/exclusion entities only.

### 6.2 Build domain/state machine

Create:

```text
backend/app/domain/builds/models.py
backend/app/domain/builds/status.py
backend/app/services/builds/service.py
backend/app/repositories/builds.py
backend/app/repositories/validation.py
```

Enforce state machine in domain/service methods, not UI alone.

### 6.3 RQ job framework

Create worker setup and jobs:

```text
backend/app/jobs/worker.py
backend/app/jobs/build.py
backend/app/jobs/index.py
backend/app/jobs/deploy.py
```

Use Redis/RQ for execution; PostgreSQL Build state is authoritative.

### 6.4 Manifest Pydantic models/JSON Schema

Create the authoritative shared contract package:

```text
packages/contracts/src/mcp_contracts/manifest_v1.py
packages/contracts/src/mcp_contracts/json_types.py
packages/contracts/schemas/mcp-manifest-v1.schema.json
packages/contracts/tests/
```

Backend domain/compiler modules may add behavior-oriented wrappers, but all serialized manifest fields/types are imported from `mcp_contracts`; do not maintain a duplicate backend manifest schema.

### 6.5 Compiler

Create:

```text
backend/app/compilers/mcp/compiler.py
backend/app/compilers/mcp/naming.py
backend/app/compilers/mcp/schema_mapping.py
backend/app/compilers/mcp/request_mapping.py
backend/app/compilers/mcp/auth_mapping.py
backend/app/compilers/mcp/resources.py
backend/app/compilers/mcp/canonicalize.py
```

Implement all compiler correctness rules and deterministic hashing.

### 6.6 Operation exclusions

Implement persistent explicit exclusion rules by operation key with reason. No silent filtering.

### 6.7 Validators

Create:

```text
backend/app/validators/source/
backend/app/validators/canonical/
backend/app/validators/coverage/
backend/app/validators/mcp/
backend/app/validators/security/
backend/app/validators/artifact/
```

Protocol validation initially may invoke an in-process runtime or test process using `McpClient`; final container protocol validation is completed in Phase 7.

### 6.8 Packaging

READY Build artifact includes:

```text
manifest.json
build-metadata.json
validation-report.json
README.md
```

No secrets.

Persist content hashes and storage keys.

### 6.9 Build API and SSE

Implement all build endpoints and progress event stream.

### 6.10 Build UI

Implement:

- build list/detail;
- stage progress;
- validation summary/findings;
- operation mapping;
- export;
- cancel where stage permits;
- no deployment button until READY.

## Tests

- state machine/property tests;
- golden compiler manifests;
- stable hashing;
- coverage 100%/exclusion rules;
- auth mapping;
- schema preservation;
- packaging no-secret scan;
- worker retry/idempotency;
- API/SSE tests.

## Phase gate

A valid project produces an immutable READY Build and exportable deterministic `mcp-manifest/v1` with 100% expected operation coverage, without yet requiring production dynamic deployment.

---

# Phase 7 — Generic MCP runtime

## Objective

Implement the reusable runtime image that serves arbitrary compatible manifests and proxies valid MCP tool calls to the declared product API.

## Dependencies

Phase 6.

## Tasks

### 7.1 Runtime manifest models

Depend directly on the infrastructure-free `packages/contracts` workspace package created in Phase 6. The runtime must import `mcp-manifest/v1` models from `mcp_contracts`; it must not copy or re-declare the manifest schema.

Implement runtime loading/validation around that shared contract:

```text
mcp_runtime/app/manifest/models.py
mcp_runtime/app/manifest/loader.py
mcp_runtime/app/manifest/schema.py
```

### 7.2 Runtime API client

Create `mcp_runtime/app/clients/api_client.py` wrapping `httpx.AsyncClient` with bounded responses, timeouts, TLS, and normalized errors.

### 7.3 Runtime URL/security policy

Create:

```text
mcp_runtime/app/security/allowlist.py
mcp_runtime/app/security/url_policy.py
mcp_runtime/app/security/redaction.py
```

Implement equivalent security contract to builder fetch policy, specialized for fixed manifest upstream hosts.

### 7.4 Upstream auth providers

Implement:

- bearer;
- API key header;
- API key query;
- Basic;
- OAuth 2 client credentials;
- static secret header.

Credentials load only from the secret bundle.

### 7.5 Request builder and executor

Create exact deterministic mapping engine from manifest tool mapping to `UpstreamRequest`.

Prohibit:

- caller host override;
- caller auth header override;
- undeclared parameters;
- unbounded body/response.

### 7.6 MCP server

Use official MCP Python SDK stable line pinned by `tech_stack.md`.

Implement exact-schema tool listing/calling using low-level/exact-schema capable server API and Streamable HTTP at `/mcp`.

Implement optional resource listing/read.

### 7.7 Inbound auth

Implement static bearer mode first as mandatory production baseline and optional external OAuth/OIDC verifier mode according to SDK support/contract.

Development no-auth mode must be explicit.

### 7.8 Health/readiness

Expose:

- process liveness;
- readiness only after manifest/secrets/registry initialization;
- no upstream mutating call for health.

### 7.9 Docker image hardening

Runtime Dockerfile:

- pinned slim Python base digest/version policy;
- non-root user;
- only runtime dependencies;
- no compiler/build tools in final stage;
- read-only-compatible filesystem;
- healthcheck;
- OCI labels/version metadata.

### 7.10 Protocol/fixture tests

Create mock upstream server fixtures in `tests/integration/mock_upstream/`.

Test:

- two materially different manifests on the same image;
- exact tool schemas;
- GET/POST/PUT/PATCH/DELETE mappings;
- path/query/body/form/multipart supported mappings;
- auth injection;
- inbound auth;
- upstream errors;
- SSRF/host override attempts;
- response limits/timeouts;
- resources;
- MCP client interoperability.

## Phase gate

The generic runtime image can serve multiple fixture manifests and external MCP clients can call tools that reach only the configured mock upstream APIs. No OpenRouter/Milvus/Postgres/Redis dependencies exist in the runtime image.

---

# Phase 8 — Dynamic deployment, Traefik routing, per-project isolation, rollback

## Objective

Deploy READY Builds as isolated project runtimes and manage lifecycle safely.

## Dependencies

Phases 1, 6, 7.

## Tasks

### 8.1 Migration 0007

Create:

- `deployments`;
- `mcp_auth_configs`;
- `mcp_access_tokens`;
- `projects.active_build_id` nullable FK to `builds.id`;
- `projects.active_deployment_id` nullable FK to `deployments.id`.

Add the two Project foreign keys only after the target tables are created within this migration/upgrade sequence, then add indexes needed for active lookups.

### 8.2 MCP access service

Implement token generation/hash/rotation/revocation and auth-mode configuration.

Plain token shown once.

### 8.3 Secret bundle materialization

Implement deployment-worker-only path that decrypts required upstream and inbound-auth secret material, writes mode-0600/controlled owner files, and mounts read-only.

### 8.4 Runtime Manager

Create:

```text
backend/app/services/deployment/runtime_manager.py
backend/app/services/deployment/service.py
backend/app/repositories/deployments.py
backend/app/jobs/deploy.py
```

Use `DockerClient` only.

### 8.5 Per-project networking

For each Project:

- create project-specific bridge network;
- connect runtime;
- connect Traefik only as required;
- do not connect runtime to builder internal network;
- clean unused network on project deletion when safe.

### 8.6 Traefik configuration

Configure base Traefik with:

- Docker provider;
- `exposedByDefault=false`;
- HTTPS entrypoint;
- production TLS/wildcard certificate instructions;
- no sensitive labels.

Runtime Manager applies labels from `design_document.md`.

### 8.7 Replacement deploy algorithm

Implement health-before-switch strategy exactly as design. If using same hostname labels would conflict, use priority/temp routing or create new runtime then update labels in controlled order; prove old runtime remains available until replacement healthy where Docker/Traefik behavior permits.

### 8.8 Stop/restart/rollback/delete

Implement lifecycle actions and durable audit.

Rollback deploys an old READY Build as a new deployment event; never changes build content.

### 8.9 Deployment API/UI

Implement:

- deployment history/status;
- endpoint copy;
- auth-mode/access token controls;
- deploy/restart/stop/rollback;
- health and runtime/build versions;
- permission handling.

### 8.10 Docker integration tests

Automated Docker-enabled test:

1. create two projects/READY fixture builds;
2. deploy two runtime containers;
3. verify unique host rules/network/resource identities;
4. connect MCP clients;
5. replace one runtime;
6. verify other unaffected;
7. rollback;
8. cleanup all resources.

## Phase gate

Ten simulated Projects can be deployed as ten independent containers/subdomains on one test host, each with separate secrets/lifecycle, while runtime containers cannot access builder data networks.

---

# Phase 9 — Complete administration UI and product workflows

## Objective

Make all core product functionality usable coherently from the browser without adding chat/SaaS concepts.

## Dependencies

Phases 2-8.

## Tasks

### 9.1 Dashboard

Display:

- project counts/status;
- builds in progress/recent failures;
- deployment health;
- OpenRouter/Milvus/system readiness;
- no customer billing metrics.

### 9.2 New-project wizard

Implement all 10 steps from `design_document.md`, resumable from durable project state.

### 9.3 Project Overview

Show:

- source status;
- latest/active build;
- validation coverage;
- deployment status;
- MCP endpoint/auth mode.

### 9.4 Operations/Tools

Table/filter/detail views with:

- source operation ID;
- method/path;
- generated tool name/title;
- input schema;
- auth mapping;
- source/enrichment descriptions;
- provenance;
- exclusion controls/reason.

### 9.5 Documentation

Show source/index generation status and document sections, safely rendered.

### 9.6 Builds/Validation/Diff

Implement detailed views with operation-level findings and historical comparison.

### 9.7 Deployments/Credentials

Finish safe secret UX, token one-time display, health/history, rollback.

### 9.8 Activity/audit

Admin filter/search by actor, project, event type, date. Never display secret payloads.

### 9.9 Settings

Implement:

- users;
- OpenRouter key/model configuration;
- embedding/index limits;
- build concurrency;
- MCP base domain display/config rules appropriate to installation;
- builders-can-deploy flag;
- retention/resource limit settings.

### 9.10 Accessibility/responsiveness

Keyboard/focus/labels/status announcements and responsive layouts validated.

## Tests

- feature/unit tests;
- permission rendering;
- secret masking;
- no chat routes/components;
- Playwright core journey.

## Phase gate

A user can complete the entire source -> READY Build -> deploy -> obtain MCP endpoint workflow through UI without terminal interaction after installation/bootstrap.

---

# Phase 10 — Diff optimization, explicit review/rebuild, export, recovery

## Objective

Complete long-term project lifecycle and reduce unnecessary build-time AI work while preserving reproducibility.

## Dependencies

Phases 5-9.

## Tasks

### 10.1 BuildDiffService

Implement structural diff model from `design_document.md`.

### 10.2 Incremental semantic reuse

Reuse prior enrichment only when:

- operation executable/source semantic fingerprint unchanged;
- relevant documentation fingerprint unchanged or prior retrieval context remains valid;
- prompt/model policy allows reuse.

Never reuse merely by operation name.

### 10.3 Explicit Review

`POST /projects/{id}/review` creates new Build and forces semantic review on current sources while preserving deterministic structural authority.

### 10.4 Explicit Rebuild

Creates a complete new Build using current compiler/runtime/prompt configuration and current source versions.

### 10.5 Export

Finalize portable bundle documentation and compatibility metadata. Include example Docker Compose fragment referencing generic runtime, but no secret values.

### 10.6 Backup/restore tooling

Provide scripts/docs for:

- PostgreSQL backup/restore;
- artifact volume backup/restore;
- master-key backup requirement;
- Milvus rebuild procedure from source/build metadata where appropriate;
- Redis non-authoritative recovery;
- redeploying active Builds after host recovery.

### 10.7 Disaster recovery test

Automated/manual runbook validation on a clean environment from backups where feasible.

## Phase gate

The platform can update, review, rebuild, export, rollback, back up, and recover projects without corrupting historical builds or requiring continuous OpenRouter usage.

---

# Phase 11 — Security, observability, performance, operational hardening

## Objective

Prove production-oriented behavior across threat, load, failure, and operational scenarios. This phase completes controls whose enabling foundations were implemented earlier; it must not defer foundational security until now.

## Dependencies

All core phases.

## Tasks

### 11.1 Threat model

Create `docs/security/threat-model.md` covering:

- malicious OpenAPI/docs;
- prompt injection in docs;
- SSRF;
- secret theft;
- Docker socket compromise;
- cross-project data leaks;
- MCP endpoint abuse;
- upstream API abuse;
- dependency/supply-chain risk;
- malicious contributor/build artifact concerns.

Map controls to code/tests.

### 11.2 Security test suite

Implement every security case in `design_document.md`.

### 11.3 Container hardening validation

Automated inspection verifies runtime:

- non-root;
- read-only root FS;
- no-new-privileges;
- dropped caps;
- no Docker socket;
- expected mounts only;
- expected networks only;
- resource limits.

### 11.4 Observability

Complete structured logging, metrics, health/readiness, request/job correlation, and dashboards/sample Prometheus configuration if provided.

### 11.5 Load/performance tests

Create reproducible performance harness for:

- API listing/navigation;
- 1,000-operation compiler;
- 10,000-doc-chunk indexing/query;
- runtime MCP call overhead;
- multiple concurrent project runtimes.

Record baselines in docs; do not hardcode environment-specific promises beyond PRD targets.

### 11.6 Failure injection

Test:

- OpenRouter down/rate-limited;
- Milvus down;
- Redis worker interruption;
- worker crash mid-build;
- Docker failure;
- runtime unhealthy replacement;
- upstream timeout;
- corrupt manifest/secret mount;
- PostgreSQL transaction failure.

Verify active runtime independence from builder AI/vector outages.

### 11.7 Dependency/SBOM/release security

Configure:

- dependency update workflow;
- vulnerability scanning;
- SBOM generation;
- secret scanning;
- image scanning;
- release artifact checksums;
- image signing if release infrastructure supports it.

## Phase gate

No known repository-controlled high/critical security issue remains; threat-model controls and PRD NFRs have evidence/tests.

---

# Phase 12 — Open-source governance, sponsorship, release readiness

## Objective

Prepare the repository and organization for public open-source collaboration and sustainable funding without introducing product entitlements.

## Dependencies

Can begin earlier, but must be complete before public stable release. Requirements are authoritative in `open_source_and_sponsorship_model.md`.

## Tasks

### 12.1 License/governance files

Add/finalize:

```text
LICENSE                         # AGPL-3.0-only
CONTRIBUTING.md
CLA.md
CODE_OF_CONDUCT.md
SECURITY.md
GOVERNANCE.md
MAINTAINERS.md
TRADEMARKS.md
SPONSORSHIP.md
SPONSORS.md
GENERATED_OUTPUTS.md
```

Do not add DCO requirements.

### 12.2 CLA automation

Configure CLA Assistant GitHub App (or the approved organization-wide CLA system) with the project's Individual CLA and Entity/Corporate CLA requirements.

Repository branch rules require the CLA status for external contributions.

Do not use the archived CLA Assistant Lite action as the primary mechanism.

### 12.3 GitHub organization controls

Configure/document:

- dedicated GitHub organization;
- protected default branch/ruleset;
- no direct pushes;
- required CI/status checks;
- required reviews/CODEOWNERS;
- 2FA organization requirement;
- least-privilege team/repository roles;
- restricted release/secrets/security-advisory permissions.

### 12.4 Funding files

Add `.github/FUNDING.yml` pointing primarily to the creator's GitHub Sponsors profile and approved personal portfolio sponsorship gateway.

Add support/sponsorship sections to README/docs without intrusive in-app monetization.

### 12.5 Sponsor recognition

Implement repository/web documentation mechanism for opt-in sponsor recognition only. Do not create a platform database entitlement model.

### 12.6 Development sponsorship policy

Document:

- anyone/company may propose sponsored development;
- founder may accept/reject before funding commitment;
- accepted work remains public and available to everyone;
- public highlight may say `Feature sponsored by Company A` if sponsor opts in;
- amount need not be public;
- sponsor receives no governance/architecture/maintainer rights.

### 12.7 Professional services/support policy

Document separation between:

- sponsorship;
- per-engagement consulting;
- future separately contracted support/SLA agreements;
- grants.

No code entitlement links.

### 12.8 Generated output policy

Make clear:

- platform/runtime are AGPL-3.0-only;
- user inputs remain user's/company's;
- project-specific generated manifests/configuration are not automatically forced under an additional restrictive license merely because the platform generated them;
- copied/derived AGPL runtime code retains AGPL;
- no secrets in exported output.

### 12.9 Release docs

Complete:

- installation;
- configuration;
- OpenRouter model setup;
- domain/TLS setup;
- API Inventory v1;
- source/auth configuration;
- build/validation/deploy;
- MCP connection examples;
- backup/restore;
- upgrade;
- security;
- contribution/governance.

## Phase gate

Repository is legally/governance-operational for external contributions under mandatory CLA and has sponsorship pathways without any paid product functionality.

---

# Phase 13 — Final integrated validation and initial stable release

## Objective

Prove the entire documentation set has been implemented with no hidden gaps.

## Dependencies

Phases 0-12.

## Integrated acceptance run

Use at least three fixture/reference projects:

### Fixture A — Standard REST API

- OpenAPI 3.0;
- bearer auth;
- GET/POST/PATCH/DELETE;
- JSON bodies;
- documentation enrichment.

### Fixture B — Complex schema API

- OpenAPI 3.1;
- nested refs;
- enums/nullable/composition;
- API key auth;
- multiple servers with explicit selected server;
- at least one explicit unsupported/excluded operation.

### Fixture C — API Inventory

- API Inventory v1;
- Basic or OAuth client-credentials auth;
- supplemental HTML/PDF/Markdown docs;
- resources generated.

For each:

1. create Project via UI/API;
2. ingest immutable sources;
3. parse/canonicalize;
4. index docs in Milvus;
5. run OpenRouter analysis using test/live release environment as appropriate;
6. compile;
7. validate 100% expected coverage;
8. export artifact and scan for secrets;
9. deploy isolated runtime/subdomain;
10. connect MCP client;
11. list tools/resources;
12. invoke read and write fixture API tools without platform HITL;
13. verify exact upstream mappings;
14. update source and rebuild;
15. inspect diff;
16. deploy new build;
17. rollback;
18. prove runtime continues during OpenRouter/Milvus outage;
19. cleanly stop/delete runtime resources.

## Repository-wide negative checks

Verify no implementation of:

- chat/conversations/agent loop;
- HITL/pending approvals;
- multi-tenancy/tenant tables;
- subscriptions/billing/entitlements;
- pgvector;
- generated per-project Python server source trees;
- OpenRouter calls from `mcp_runtime/`;
- Milvus dependency in `mcp_runtime/`;
- Docker SDK calls outside approved `DockerClient` integration path;
- direct Redis/Milvus/OpenRouter SDK use from service/router code;
- DCO enforcement.

## Final quality gates

All must pass:

- Ruff/lint/format;
- Python type checks;
- frontend lint/type checks;
- backend unit tests;
- runtime unit tests;
- frontend unit tests;
- parser golden tests;
- compiler golden tests;
- integration tests;
- Milvus tests;
- Docker deployment tests;
- MCP protocol tests;
- Playwright E2E;
- security suite;
- dependency/image scans;
- migrations upgrade from empty database;
- backup/restore drill;
- documentation link/command checks.

## Initial stable release completion criteria

The project is implementation-complete only when:

1. every Product Requirement marked core is implemented;
2. all architecture completion criteria pass;
3. all design completion criteria pass;
4. every phase gate has evidence;
5. all required tests pass from a clean checkout;
6. all migrations work from an empty PostgreSQL 18 database and documented supported upgrade state;
7. a fresh Docker Compose installation completes the full fixture flow;
8. no production TODO/stub/parallel replacement remains;
9. open-source governance/CLA/sponsorship documentation is present and enforced;
10. known external-only limitations are clearly documented and no repository-controlled blocker is mislabeled as external.

---

## 4. Migration plan summary

Migration numbering may be consolidated during initial greenfield implementation, but the logical order must remain:

1. users/auth/settings/audit;
2. projects/sources/source_versions/credentials;
3. canonical snapshots;
4. document index generations;
5. builds/build-source links/build AI runs;
6. validation reports/operation exclusions;
7. deployments/MCP auth configs/access tokens/active project references;
8. later indexes/constraints added by measured need.

If all migrations are authored before public release, squashing into a clean initial migration is allowed only before any released database version exists. After first public release, never rewrite released migration history.

---

## 5. Required implementation evidence

The coding agent shall maintain objective evidence during implementation, ideally under `docs/evidence/` or linked PR/release reports:

- command outputs/test summaries;
- representative validation report;
- fixture manifest hashes;
- Docker/runtime isolation inspection;
- MCP protocol results;
- security test results;
- performance baseline;
- migration checks;
- no-secret artifact scan;
- dependency/SBOM scan;
- final requirement traceability matrix.

Do not consider prose claims such as “implemented” sufficient when a test or inspectable artifact can prove the requirement.

---

## 6. Requirement traceability

Before release, create a machine-readable or Markdown traceability matrix mapping:

```text
PRD requirement ID
-> implementation module(s)
-> test(s)
-> status
-> evidence/reference
```

Every `FR-*` and release-blocking `NFR-*` from `product_requirements.md` must have at least one implementation/test reference or an explicit justified not-applicable designation consistent with the docs.
