# MCPlica Architecture

**Status:** Authoritative implementation specification  
**Date:** 2026-08-24  
**Applies to:** The complete self-hosted API-to-MCP platform and generated MCP runtimes

## 1. Document ownership

This document owns the **system architecture**: system boundaries, major components, responsibilities, communication paths, data flows, runtime topology, external integrations, deployment model, isolation model, and architectural decisions.

Do not place implementation-level class signatures, database column-by-column definitions, or detailed REST payloads here; those belong to `design_document.md`. Product scope and acceptance behavior belong to `product_requirements.md`. Technology/version choices belong to `tech_stack.md`. Sequencing belongs to `implementation_plan.md`. Open-source governance belongs to `open_source_and_sponsorship_model.md`.

If implementation behavior conflicts with an architectural rule in this file, this file is authoritative for architecture.

---

## 2. System purpose

The platform is a **self-hosted, open-source, AI-assisted API-to-MCP compiler, validator, builder, and deployment manager**.

A company provides one product at a time through:

- an OpenAPI specification, or
- a structured API inventory,
- optionally supplemented by API/product documentation.

The platform analyzes the supplied material, constructs a normalized canonical API representation, enriches semantic information using OpenRouter and retrieval from Milvus, deterministically compiles an MCP-equivalent representation, validates coverage and consistency, and deploys the product as an isolated MCP runtime reachable at its own subdomain.

The company then connects that MCP endpoint to **its own MCP host, agent, IDE, AI provider, or other MCP-compatible client**.

The platform does **not** provide a chat interface or an end-user agent runtime.

---

## 3. Non-negotiable architectural constraints

1. **Self-hosted, not SaaS.** The product is installed and operated by its user/company.
2. **No multi-tenancy abstraction.** There is no tenant, organization billing account, subscription, entitlement, or plan model in the application.
3. **One installation may contain many projects.** Each project represents one source company product/API converted to MCP.
4. **One isolated MCP deployment per project.** Ten imported products mean ten independently addressable MCP runtimes and ten MCP subdomains.
5. **No built-in chat.** The platform does not own conversations, agent memory, chat sessions, or end-user model usage.
6. **No HITL or approval engine for MCP calls.** The generated MCP server faithfully exposes allowed API capabilities. Any approval policy belongs to the consuming MCP host/agent.
7. **OpenRouter is build-time intelligence only.** OpenRouter may analyze, enrich, review, generate structured semantic metadata, validate, and create embeddings during a build/rebuild. Generated MCP runtimes must not require OpenRouter.
8. **Milvus is builder-side semantic infrastructure only.** Generated MCP runtimes must not require Milvus.
9. **Manifest-driven runtime.** The system must not generate a separately maintained Python application for every project. It compiles project-specific manifests/configuration and runs them on a reusable generic MCP runtime image.
10. **Deterministic structure, AI-assisted semantics.** HTTP methods, paths, schemas, security schemes, required fields, response structures, and executable mappings come from deterministic source parsing and validation. AI may enrich descriptions and semantic relationships but may not invent executable API behavior.
11. **At least one executable source is required.** A project must contain either a valid OpenAPI source or a valid API Inventory source. Documentation alone is not sufficient to produce a deployable MCP server.
12. **Client-based integration architecture.** Every infrastructure/external integration is accessed through a dedicated client abstraction (database, Redis, Milvus, OpenRouter, HTTP, Docker, MCP, storage, etc.). Business services do not directly instantiate SDK clients.
13. **PostgreSQL is authoritative state.** Redis is temporary/cache/queue state. Milvus is semantic index state and is rebuildable from authoritative project sources.
14. **No source API side effects during build.** The builder validates specifications and generated MCP behavior without autonomously invoking company business operations. Runtime calls occur only when an external MCP client calls a published MCP tool.
15. **Security boundaries are fail-closed.** Missing credentials, invalid source mappings, unsupported schemas, invalid deployment state, or uncertain executable mappings fail a build or disable the affected operation rather than guessing.

---

## 4. System context

```text
 Company Admin / Builder
          |
          | HTTPS
          v
+--------------------------------------------------------------+
|                     BUILDER / CONTROL PLANE                  |
|                                                              |
| React + TypeScript + Vite + Tailwind + shadcn/ui            |
|                         |                                    |
|                         v                                    |
|                      FastAPI                                 |
|                         |                                    |
|   +---------------------+-------------------------------+    |
|   |                     |               |               |    |
|   v                     v               v               v    |
| PostgreSQL            Redis           Milvus        OpenRouter|
| authoritative       cache/queue    vectors/RAG    build-time AI|
|                                                              |
|                         |                                    |
|                         v                                    |
|                  Runtime Manager                             |
|                         | Docker Engine                       |
+-------------------------+------------------------------------+
                          |
                          | create/configure/deploy
                          v
+--------------------------------------------------------------+
|                        MCP SERVING PLANE                     |
|                                                              |
|                           Traefik                            |
|                             |                                |
|         +-------------------+-------------------+            |
|         |                   |                   |            |
|         v                   v                   v            |
| crm.mcp.domain      hr.mcp.domain      inventory.mcp.domain  |
| MCP Runtime         MCP Runtime         MCP Runtime           |
|     |                   |                   |                 |
|     v                   v                   v                 |
| CRM product API     HR product API     Inventory product API  |
+--------------------------------------------------------------+
             ^
             |
             | MCP Streamable HTTP
             |
     Company-owned MCP hosts / agents / IDEs / AI systems
```

---

## 5. Architectural planes

### 5.1 Builder / Control Plane

The Builder Plane owns project lifecycle and MCP creation. It is a modular monolith composed of a FastAPI backend, a browser-based administration UI, PostgreSQL, Redis, Milvus, background workers, and external OpenRouter access.

It owns:

- user authentication and installation-level authorization;
- project lifecycle;
- source ingestion/versioning;
- OpenAPI and API Inventory parsing;
- documentation parsing and semantic indexing;
- canonical API representation;
- OpenRouter-assisted semantic analysis/enrichment/review;
- deterministic MCP compilation;
- build/version management;
- validation and coverage reports;
- deployment lifecycle;
- credentials and secret handling;
- exportable MCP artifacts;
- audit history for platform changes.

It does not own end-user AI conversations or runtime agent policy.

### 5.2 MCP Serving Plane

The Serving Plane consists of independently deployed project runtimes.

Each runtime:

- exposes MCP using Streamable HTTP;
- loads a project-specific immutable MCP manifest;
- lists the tools/resources defined by that manifest;
- validates incoming tool arguments against the manifest schema;
- translates a valid MCP tool call into exactly one configured API operation or an explicitly modeled deterministic execution mapping;
- injects target product credentials without exposing them to the MCP caller;
- calls only the configured target API hosts and operations;
- returns structured MCP results/errors;
- exposes health status;
- emits sanitized operational logs;
- contains no build-time AI dependency.

The runtime is intentionally small and generic.

---

## 6. Core domain concept: Project

A **Project** is the root aggregate representing one company product/API being converted into MCP.

A Project owns relationships to:

```text
Project
├── identity and configuration
├── source versions
│   ├── OpenAPI source(s)
│   ├── API Inventory source(s)
│   └── documentation source(s)
├── canonical API snapshots
├── semantic index namespace
├── builds
│   ├── analysis snapshots
│   ├── MCP manifest
│   ├── validation report
│   └── export artifact
├── target API credentials
├── MCP inbound access configuration
└── deployment(s)
    └── active deployment
```

`ProjectService` coordinates project lifecycle. It must not parse OpenAPI, call OpenRouter, operate Milvus, or manage Docker directly. Those responsibilities remain in specialized components described below.

---

## 7. Builder Plane components

### 7.1 Web UI

The UI is an administrative/build interface, not a customer-facing chat product.

Primary areas:

- Dashboard
- Projects
- Project import/setup wizard
- Sources
- Documentation
- API operations/tools
- Builds
- Validation reports
- Deployments
- Credentials and MCP access
- Activity/audit
- System settings

The UI communicates only with the FastAPI application API.

### 7.2 FastAPI application

FastAPI is the application boundary for browser/API requests. API routers are thin and must delegate to application services.

Responsibilities:

- authentication/authorization;
- request validation;
- invoking application services;
- returning versioned REST resources;
- streaming build/deployment progress events;
- health/readiness endpoints.

Routers must not contain database queries, Docker SDK operations, raw Redis commands, OpenRouter calls, or Milvus operations.

### 7.3 Project Service

Owns project identity/lifecycle and coordinates domain-level relationships.

It may invoke:

- `SourceService`
- `BuildService`
- `DeploymentService`
- `CredentialService`

It does not implement those components' internals.

### 7.4 Source Ingestion subsystem

Accepts, validates, fingerprints, versions, and stores source material.

Supported authoritative executable source types:

- OpenAPI 3.0.x JSON/YAML
- OpenAPI 3.1.x JSON/YAML
- API Inventory v1 JSON/YAML defined by this project

Supported supplemental documentation sources are defined in `design_document.md`.

Every source version is immutable after ingestion. Replacing a source creates a new source version.

### 7.5 OpenAPI / API Inventory parser and normalizer

This subsystem is deterministic.

It:

- validates source syntax and specification version;
- resolves local and permitted remote references using controlled fetch rules;
- extracts servers/base URLs;
- extracts security schemes;
- extracts operations, paths, methods, parameters, request bodies, responses, schemas, tags, examples, and descriptions;
- generates stable identifiers when necessary;
- rejects contradictory or unsupported executable definitions;
- outputs the canonical API model.

The canonical model is the sole executable input to the MCP compiler. The compiler does not read raw OpenAPI directly.

### 7.6 Documentation ingestion and semantic indexing

Documentation is parsed, normalized, chunked, embedded through the configured OpenRouter embedding model, and indexed in Milvus under a project/build-aware namespace.

Documentation may improve:

- operation descriptions;
- terminology;
- semantic relationships;
- tool categorization;
- resource generation;
- validation context.

Documentation may **not** silently create executable endpoints that do not exist in an OpenAPI or API Inventory source.

### 7.7 OpenRouter analysis/enrichment subsystem

OpenRouter is invoked only by background build/review jobs.

It is used for:

- semantic classification;
- business terminology extraction;
- documentation-to-operation correlation;
- description enrichment;
- tool title/summary refinement;
- ambiguous-but-non-executable semantic interpretation;
- semantic validation and review;
- structured build quality findings.

Every AI response used by the build pipeline must use a declared structured-output schema where the selected model supports it, then be parsed into Pydantic models. Unstructured prose must never directly alter executable mappings.

AI model IDs, prompt/template version, source fingerprints, retrieved context IDs, and response metadata must be recorded on the build for reproducibility/audit.

### 7.8 Canonical API Model

The canonical API model separates source format from generation format.

It models, at minimum:

- API identity;
- base servers;
- authentication/security requirements;
- operations;
- stable operation IDs;
- HTTP method/path;
- path/query/header/cookie parameters;
- request body media types and JSON Schemas;
- response status/media types and JSON Schemas;
- tags/categories;
- descriptions and semantic metadata;
- source provenance for every executable field;
- build-time enrichment metadata separately from source-derived executable metadata.

No AI-produced field may overwrite source-derived executable structure without an explicit deterministic rule.

### 7.9 MCP Compiler

The MCP Compiler transforms a validated canonical API snapshot into a versioned MCP definition/manifest.

Compilation is deterministic for identical canonical input and compiler version.

It owns:

- stable tool naming;
- MCP tool metadata;
- tool input schemas;
- output/response metadata;
- HTTP request mapping;
- authentication mapping references;
- MCP resource definitions derived from documentation where configured;
- runtime policy metadata such as allowed upstream hosts, timeout limits, payload limits, and operation enablement.

The compiler does not generate arbitrary per-project Python source code. The serialized MCP manifest contract is defined once in an infrastructure-free shared Python package consumed by both builder/compiler and generic runtime so the two sides cannot drift independently.

### 7.10 Validation subsystem

Validation is multi-layered:

1. **Source validation** — source syntax/specification is valid.
2. **Canonical validation** — normalized model is internally consistent.
3. **Coverage validation** — every intended operation is generated or has an explicit exclusion reason.
4. **Schema validation** — MCP inputs map losslessly enough to source parameters/request bodies.
5. **Security mapping validation** — required upstream auth schemes have valid runtime mappings.
6. **Semantic validation** — AI-assisted review checks descriptions/relationships without overriding deterministic evidence.
7. **MCP protocol validation** — the generated manifest can be served by the generic runtime and inspected through an MCP client/Inspector test harness.
8. **Artifact validation** — manifest hashes, runtime compatibility, and exported bundle structure are valid.

A build cannot become `ready` unless all blocking deterministic validators pass.

### 7.11 Build Service

A Build is an immutable attempt to compile a Project source snapshot into a deployable MCP artifact.

Builds are processed asynchronously by workers and are versioned.

Each build records:

- exact source versions;
- canonical snapshot hash;
- documentation index generation ID;
- compiler version;
- MCP runtime compatibility version;
- AI provider/model identifiers;
- prompt/template versions;
- validation results;
- manifest hash;
- artifact hash;
- timestamps/status/error metadata.

An explicit review/rebuild creates a new Build; it does not mutate a prior successful build.

### 7.12 Diff/Rebuild subsystem

When source material changes, the build system computes structural and semantic diffs:

- added operations;
- removed operations;
- changed operations;
- changed schemas;
- changed auth schemes;
- changed documents/chunks;
- unchanged operations.

AI re-analysis should be limited to changed/affected context whenever correctness permits. Unchanged deterministic artifacts may be reused by hash, but the final build remains independently reproducible.

### 7.13 Deployment Service / Runtime Manager

Deployment is separate from compilation.

The Deployment Service requests deployment work. The Runtime Manager/worker is the only component permitted to manage Docker Engine resources.

It:

- creates runtime configuration files and secret mounts;
- creates per-project container/network resources;
- starts/stops/restarts/replaces the generic MCP runtime image;
- assigns Traefik labels;
- performs health/readiness checks;
- records container/image/manifest identity;
- supports rollback to a previous successful build;
- removes superseded runtime resources safely.

The FastAPI web process must not require direct Docker socket access.

### 7.14 Export Service

A user may export a project-specific MCP bundle containing non-secret project artifacts and instructions for running them outside the control plane.

The bundle must never include plaintext target API credentials or MCP access secrets.

The generic runtime remains separately versioned software; generated project-specific manifest/configuration ownership is governed by `open_source_and_sponsorship_model.md`.

---

## 8. Integration architecture: clients, providers, repositories, services

All external systems are reached through explicit coding clients.

```text
API Router / Job
      |
      v
Application Service
      |
      +--> Domain Repository ------> DatabaseClient ------> PostgreSQL
      |
      +--> Provider ---------------> Provider Client ----> External API
      |
      +--> Cache/Vector abstraction -> Dedicated Client --> Redis/Milvus
      |
      +--> Deployment abstraction --> DockerClient ------> Docker Engine
```

Required client families:

- `DatabaseClient`
- `RedisClient`
- `MilvusClient`
- `HttpClient`
- `OpenRouterClient`
- `DockerClient`
- `McpClient`
- `StorageClient`

Provider abstractions exist where product-level semantics must be separated from transport details, including at least:

- `AIProvider` -> `OpenRouterProvider`
- `VectorStore` -> `MilvusVectorStore`
- `ArtifactStorage` -> local filesystem implementation initially

Repositories own domain queries; `DatabaseClient` owns engine/session/transaction mechanics only.

---

## 9. Data ownership

### PostgreSQL — authoritative

Stores durable platform/domain state:

- users/auth metadata;
- projects;
- source metadata and versions;
- canonical snapshot metadata/serialized structures where appropriate;
- builds;
- validation reports;
- deployments;
- encrypted credential records;
- MCP access-token metadata;
- audit/activity events;
- system model/configuration metadata.

### Redis — non-authoritative

Stores only rebuildable or transient state:

- RQ queues/jobs;
- build/deployment progress;
- short-lived locks;
- idempotency keys;
- cache entries;
- model/catalog cache;
- progress event fan-out.

Redis loss may interrupt active jobs but must not lose authoritative project/build state.

### Milvus — semantic index

Stores vectors and searchable metadata derived from project documentation/source descriptions.

Milvus data must be rebuildable from source versions and embedding configuration. PostgreSQL records the index generation and embedding model/dimension required to interpret it.

### Artifact storage — local filesystem in V1

Stores immutable source blobs and generated/export artifacts under controlled paths/volumes. Database rows reference content hashes and storage keys. A future object-storage provider may be added through the storage abstraction without changing domain behavior.

---

## 10. Build-time data flow

```text
Upload OpenAPI/API Inventory + docs
              |
              v
       Source Ingestion
              |
      immutable versions/hash
              |
              v
  Deterministic Parse/Normalize
              |
              v
      Canonical API Model
              |
        +-----+-----------------------+
        |                             |
        v                             v
Documentation parse/chunk        deterministic source facts
        |
        v
OpenRouter embeddings
        |
        v
      Milvus
        |
        +-----------> Retrieval context
                           |
                           v
                     OpenRouter analysis
                           |
                           v
                 typed semantic enrichment
                           |
                           v
                  Enriched canonical view
                           |
                           v
                   Deterministic compiler
                           |
                           v
                      MCP manifest
                           |
                           v
                    Validation suite
                           |
                           v
                    Immutable build
```

No step in this flow performs autonomous business operations against the source company's product API.

---

## 11. Runtime MCP-call data flow

```text
Company MCP Host
       |
       | Streamable HTTP + MCP auth
       v
Traefik -> Project MCP Runtime
                  |
                  | validate tool name + input schema
                  v
              Tool Registry
                  |
                  v
             Request Builder
                  |
                  v
          Upstream Auth Provider
                  |
                  v
              ApiClient
                  |
                  | exact configured method/path/host
                  v
          Company Product API
                  |
                  v
        sanitized/structured result
                  |
                  v
           MCP CallToolResult
                  |
                  v
          Company MCP Host
```

The MCP runtime never asks OpenRouter whether or how to execute a call. Execution mapping is fully determined by the manifest.

---

## 12. MCP runtime model

### 12.1 Generic reusable image

All project containers run the same compatible runtime image family, for example conceptually:

```text
api-to-mcp/mcp-runtime:<semver>
```

A project's behavior comes from its immutable manifest plus secret/configuration mounts.

### 12.2 MCP SDK level

The runtime uses the official Python MCP SDK and Streamable HTTP. It must use a server layer that allows exact generated JSON Schemas to be published rather than deriving tool schemas from handwritten Python function signatures.

The current official Python SDK documents a stable v2 line and supports Streamable HTTP; its low-level server explicitly supports exact schemas loaded from generated data. The implementation must pin a tested SDK release through the dependency lockfile and maintain an explicit runtime/manifest compatibility version.

### 12.3 Tool mapping

One source API operation normally compiles to one MCP tool unless explicitly excluded or intentionally combined by a deterministic, documented compiler rule.

The runtime must not construct arbitrary URLs from LLM-provided text. Host, HTTP method, and path template come from the manifest. Call arguments only provide declared parameter/body values.

### 12.4 Resources

Supplemental documentation may be exposed as MCP resources when useful. Resources are non-executable context and must retain source provenance.

### 12.5 No prompts requirement

MCP prompts are optional and are not required for the core product. The primary generated primitives are tools and resources.

---

## 13. Authentication boundaries

There are two independent authentication directions.

### 13.1 MCP client -> generated MCP runtime

This protects the published MCP endpoint.

Production deployments must not be anonymously exposed by default.

Required architecture:

- per-project inbound MCP authentication configuration;
- static high-entropy bearer access tokens as the baseline interoperable mode;
- token values shown once on creation/rotation and stored only as hashes in control-plane metadata;
- runtime receives the necessary verifier material through a secret mount;
- optional external OAuth/OIDC token-verifier mode may be configured without changing tool semantics;
- authentication disabled only through an explicit development-mode setting.

### 13.2 Generated MCP runtime -> product API

The project owns a target API credential configuration mapped from supported source security schemes.

Initial supported upstream auth families:

- bearer token;
- API key header;
- API key query parameter;
- HTTP Basic;
- OAuth 2 client credentials;
- static custom headers that are explicitly configured as secrets.

Credential values never become MCP tool arguments and are never emitted in manifests/logs/export bundles.

---

## 14. Network and SSRF boundary

The runtime must use an allowlisted upstream-host policy generated from the Project configuration/source servers.

Rules:

- tool calls cannot provide arbitrary scheme/host/port;
- redirects are disabled by default or revalidated against the allowlist before following;
- link-local, loopback, Docker socket, Unix socket, and cloud metadata destinations are blocked unless the entire installation explicitly operates in a development/test mode that names the destination;
- DNS resolution must be rechecked before connect where practical to reduce DNS-rebinding risk;
- URL path construction must prevent path traversal and host injection;
- headers controlled by callers cannot overwrite authorization/host/hop-by-hop security headers unless the manifest explicitly allows the field.

Builder-side remote source/document URL fetching uses the same SSRF principles.

---

## 15. Deployment topology

Base installation through Docker Compose:

```text
traefik
frontend
api
worker
postgres
redis
milvus
milvus supporting services required by the selected standalone release
```

Generated MCP runtime containers are dynamic Docker resources managed by the Runtime Manager and are not statically enumerated in the base Compose file.

### 15.1 Domain convention

The installation defines:

```text
MCP_BASE_DOMAIN=mcp.example.com
```

A project slug `inventory` receives:

```text
https://inventory.mcp.example.com/mcp
```

Wildcard DNS and TLS are the preferred production deployment model.

### 15.2 Traefik

Traefik is the edge reverse proxy and Docker-aware route provider.

Required configuration principles:

- Docker provider enabled;
- `exposedByDefault=false`;
- only explicitly labeled MCP containers are routed;
- credentials/secrets never stored in labels;
- explicit router/service names generated from stable project IDs;
- HTTPS in production;
- project hostname maps to runtime `/mcp` endpoint.

### 15.3 Container isolation

Each project runtime has:

- its own container;
- its own immutable manifest mount;
- its own secret mount;
- its own runtime identity/name;
- its own resource limits;
- its own health status;
- its own subdomain;
- a project-specific Docker network containing only the runtime and the Traefik attachment needed to reach it;
- no connection to PostgreSQL, Redis, Milvus, builder internal networks, or the Docker socket.

Runtime hardening baseline:

- non-root user;
- read-only root filesystem;
- `no-new-privileges`;
- Linux capabilities dropped unless strictly required;
- controlled writable temporary directory;
- CPU/memory/PID limits;
- no host network;
- no privileged mode;
- no Docker socket;
- bounded request/response sizes and timeouts.

---

## 16. Docker authority boundary

The Docker socket is privileged and is not mounted into the browser-facing FastAPI API container.

```text
FastAPI -> durable job request -> Worker/Runtime Manager -> DockerClient -> Docker Engine
```

Only the deployment worker/runtime-manager process receives the minimal Docker API access required to create/manage project runtimes. Production documentation must recommend a Docker socket proxy or equivalent constrained access if supported by the installation environment.

---

## 17. Reliability model

### Builder Plane

- Build and deploy operations are asynchronous and idempotent by stable job keys.
- Durable state transitions are written to PostgreSQL before/after external side effects.
- Workers may retry transient OpenRouter, Redis, Milvus, filesystem, or Docker failures using bounded exponential backoff.
- Deterministic validation failures are not retried automatically.
- A crashed worker may resume/retry an interrupted build from durable stage boundaries, but must never mutate a completed build.
- Failed builds do not replace the active deployed build.

### Serving Plane

- A runtime failing startup/manifest validation must remain unhealthy and must not receive production traffic.
- Deployment replacement uses health-before-switch semantics where feasible.
- Rollback redeploys a previously validated immutable build.
- Runtime API errors are mapped to MCP-readable error results without leaking credentials or internal traces.

---

## 18. Observability architecture

The control plane emits structured logs with correlation IDs for:

- user/API request;
- project;
- build;
- job;
- deployment.

The runtime emits structured logs with:

- project/build/runtime identifiers;
- MCP request ID if available;
- tool name;
- upstream operation ID;
- duration/status;
- sanitized error category.

Never log:

- API keys;
- bearer tokens;
- passwords;
- OAuth secrets/tokens;
- raw Authorization headers;
- full sensitive request/response bodies by default.

Audit events are durable for control-plane changes such as credentials rotation, deployment, rollback, source changes, settings changes, and access-token changes.

---

## 19. Scaling model

The initial deployment target is one Docker host using Docker Compose plus dynamic runtime containers.

The architecture scales vertically first and horizontally only where justified:

- multiple worker processes may consume Redis/RQ jobs;
- PostgreSQL, Redis, and Milvus may be externalized later through unchanged clients/providers;
- artifact storage may move from local filesystem to object storage through the storage abstraction;
- runtime containers scale independently by project if a future deployment provider implements replicas;
- a future Kubernetes deployment provider may implement the same deployment interface, but Kubernetes is explicitly not required for the initial product.

No Kafka, service mesh, distributed microservice topology, or separate API gateway is required.

---

## 20. Architectural decisions

### ADR-001 — Modular monolith for the Builder Plane

**Decision:** One FastAPI backend codebase with explicit domain modules and background workers.  
**Reason:** The product is self-hosted and operational simplicity is more important than premature service decomposition.

### ADR-002 — Separate Builder and Serving planes

**Decision:** Build-time AI/indexing infrastructure is separate from deployed MCP runtimes.  
**Reason:** Runtime MCP availability must not depend on OpenRouter, Milvus, builder UI, or build workers.

### ADR-003 — Manifest-driven generic MCP runtime

**Decision:** Compile project-specific manifests rather than generated project-specific Python code.  
**Reason:** Security fixes/runtime upgrades apply to all projects; builds stay reproducible; generated output remains inspectable.

### ADR-004 — Deterministic compiler authority

**Decision:** AI may enrich semantics but cannot define executable source structure without deterministic evidence.  
**Reason:** Prevent hallucinated endpoints/parameters/security behavior.

### ADR-005 — Milvus, not pgvector

**Decision:** Milvus is the vector database. PostgreSQL does not carry vector-search responsibility.  
**Reason:** Explicit project decision and clean separation of semantic retrieval from relational truth.

### ADR-006 — OpenRouter only during builds/reviews

**Decision:** OpenRouter powers analysis, structured enrichment, semantic review, and embeddings but is absent from generated runtime dependencies.  
**Reason:** The project builds MCP servers; it is not itself the downstream AI host.

### ADR-007 — Dedicated clients for infrastructure

**Decision:** Services use clients/providers/repositories rather than direct third-party SDK calls.  
**Reason:** Testability, replacement, consistency, observability, and failure isolation.

### ADR-008 — Per-project runtime isolation and subdomains

**Decision:** Every active project has a separate runtime and subdomain.  
**Reason:** Independent lifecycle, credentials, logs, health, and blast radius.

### ADR-009 — No HITL policy engine

**Decision:** The platform/runtime does not require human approval before executing a valid MCP tool request.  
**Reason:** Approval is an agent/host responsibility, not API-to-MCP conversion responsibility.

### ADR-010 — No chat product

**Decision:** No built-in chat/agent session architecture.  
**Reason:** The product terminates at a standards-based MCP endpoint.

### ADR-011 — Docker Compose first

**Decision:** Base platform runs via Docker Compose; generated servers are dynamically managed Docker containers routed by Traefik.  
**Reason:** Appropriate complexity for self-hosted open source and matches deployment requirements.

### ADR-012 — PostgreSQL authority / Redis transient / Milvus rebuildable

**Decision:** Each data store has a single clearly bounded responsibility.  
**Reason:** Avoid split-brain domain state and simplify disaster recovery.

---

## 21. Explicitly excluded architectures

The implementation must not introduce these without a later authoritative documentation change:

- multi-tenant SaaS architecture;
- subscriptions, payment plans, metering, or entitlements;
- user-facing chat/agent orchestration;
- HITL approval workflows for MCP calls;
- one generated Python repository per imported API;
- runtime dependency on OpenRouter;
- runtime dependency on Milvus;
- pgvector;
- Kubernetes as a required deployment path;
- Kafka/RabbitMQ/event bus infrastructure;
- LangChain/LangGraph as core architecture;
- database-per-project;
- Redis-per-project;
- microservice decomposition of the Builder Plane.

---

## 22. Architecture completion criteria

The architecture is correctly implemented only when all of the following are demonstrably true:

1. A clean installation starts the builder/control plane through Docker Compose.
2. A user can create multiple Projects without any tenant/subscription model.
3. OpenAPI/API Inventory sources are parsed into a canonical model before MCP compilation.
4. Documentation semantic search uses Milvus and is absent from generated MCP runtime dependencies.
5. OpenRouter is invoked only during build/review/indexing workflows and never during external MCP tool calls.
6. Identical canonical input/compiler versions yield identical executable MCP manifest structure.
7. The same generic runtime image can run at least two materially different project manifests.
8. Two projects can be deployed simultaneously to two distinct subdomains with distinct secrets and independent health/lifecycle.
9. Runtime containers cannot reach builder databases/caches/vector stores through application networks and do not have Docker socket access.
10. MCP clients can list tools and call a generated tool using Streamable HTTP, causing the runtime to invoke only the configured upstream operation.
11. The builder exposes no chat/conversation/agent product surface.
12. No MCP execution approval/HITL state exists in the runtime or control-plane domain.
13. Failed new builds/deployments do not corrupt or silently replace a previously healthy active deployment.
14. Build artifacts, source versions, validation reports, and deployments are traceable by immutable IDs/hashes.
15. All external integrations are accessed through the documented client/provider/repository boundaries.

---

## 23. External standards baseline

Implementation must track tested stable releases rather than unpinned latest versions. At this specification date:

- the official MCP Python SDK documents v2 as the current stable release line and supports Streamable HTTP and exact-schema low-level server usage;
- OpenRouter provides structured-output JSON Schema responses and an embeddings API suitable for the build pipeline;
- Milvus supports standalone Docker Compose deployment;
- Traefik's Docker provider supports dynamic routing from Docker labels and recommends keeping sensitive data out of labels.

Technology pinning and upgrade policy are authoritative in `tech_stack.md`.
