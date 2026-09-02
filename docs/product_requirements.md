# MCPlica Product Requirements

**Status:** Authoritative product specification  
**Date:** 2026-08-24  
**Product category:** Self-hosted open-source API-to-MCP builder and serving platform

## 1. Document ownership

This document owns the **product definition**: vision, goals, users, problems, use cases, capabilities, functional requirements, non-functional requirements, constraints, acceptance criteria, and explicit out-of-scope behavior.

Technical architecture belongs to `architecture.md`; implementation mechanics to `design_document.md`; technology standards to `tech_stack.md`; sequencing to `implementation_plan.md`; open-source funding/governance to `open_source_and_sponsorship_model.md`.

---

## 2. Product vision

Companies already have valuable products and APIs, but those capabilities are usually usable only by developers, operations staff, or technically experienced people. AI agents and MCP-capable applications can make those product capabilities accessible through natural-language and agent workflows, but manually building and maintaining a correct MCP layer for every existing API is expensive and repetitive.

The product shall let a company take an existing product/API description and **convert it into a production-oriented MCP equivalent with minimal manual engineering**.

The platform is not the company's AI agent. It produces and serves the MCP capability layer that the company connects to whichever MCP host, agent, IDE, AI platform, or internal automation it chooses.

### Product statement

> A self-hosted, open-source platform that ingests a company's OpenAPI specification or structured API inventory, optionally incorporates product/API documentation, uses AI only during analysis and build/review, deterministically compiles the result into an MCP-equivalent server, validates coverage/correctness, and deploys each product as an isolated MCP endpoint.

---

## 3. Primary product goals

### G-01 — Make existing APIs directly consumable as MCP

A company must be able to transform an existing API definition into an MCP server without hand-writing an MCP tool implementation for every endpoint.

### G-02 — Preserve API fidelity

The generated MCP surface must faithfully represent source operations, parameter requirements, schemas, authentication requirements, and documented semantics. The product must prefer blocking/exclusion over guessing.

### G-03 — Use AI where it adds value, not where determinism is required

OpenRouter shall improve semantic understanding, documentation correlation, descriptions, classification, review, and build quality. It shall not decide runtime execution dynamically.

### G-04 — Produce independently usable MCP endpoints

Generated runtimes must continue operating without OpenRouter, Milvus, or a built-in platform chat feature.

### G-05 — Isolate company products

Each project/product gets its own MCP runtime, credentials, lifecycle, subdomain, health state, and deployment identity.

### G-06 — Make rebuilds safe and auditable

Source changes and explicit reviews/rebuilds create immutable new builds, report differences, and never silently corrupt the active deployment.

### G-07 — Remain straightforward to self-host

The primary deployment path shall be Docker/Docker Compose, not Kubernetes or a complex distributed platform.

### G-08 — Remain fully open source

All product functionality remains available in the open-source codebase. Funding and commercial services do not create a feature-gated edition. Governance is defined in `open_source_and_sponsorship_model.md`.

---

## 4. Product success outcomes

The product is successful when an administrator can:

1. install the platform on a Docker host;
2. configure OpenRouter once for build intelligence;
3. create a project for a company product;
4. upload/fetch an OpenAPI 3.x specification or API Inventory v1;
5. optionally add product/API documentation;
6. configure source API server and authentication;
7. run an automated analysis/build;
8. inspect exact source-to-MCP coverage and validation findings;
9. deploy the build;
10. receive an MCP endpoint such as `https://inventory.mcp.example.com/mcp`;
11. configure MCP inbound authentication;
12. connect an external MCP client/agent and list/call the generated tools;
13. update the API source later and rebuild/redeploy with a visible diff and rollback path.

---

## 5. Target users

### 5.1 Installation Administrator

Technical owner of the self-hosted platform.

Needs to:

- install/upgrade the platform;
- manage users and system configuration;
- configure OpenRouter;
- manage deployment/network/domain settings;
- manage/rotate sensitive project credentials;
- view platform health/audit events.

### 5.2 API/MCP Builder

A developer, platform engineer, operations engineer, product engineer, or technical administrator converting APIs to MCP.

Needs to:

- create projects;
- add/update source material;
- inspect discovered operations;
- build/review/rebuild;
- understand validation failures;
- compare versions;
- deploy when permitted;
- obtain connection information for downstream MCP consumers.

### 5.3 Downstream MCP Consumer

This is **not a platform user persona inside the UI**. It is an external MCP-capable system owned/selected by the company, such as an AI agent, IDE, automation, or other MCP host.

Needs:

- a standards-compatible MCP endpoint;
- authentication credentials/configuration;
- stable tools and descriptions;
- predictable runtime behavior.

---

## 6. Core product objects

### 6.1 Project

Represents one company product/API to be converted and served as MCP.

### 6.2 Source

Logical input source for a project, with immutable versions. Types:

- OpenAPI;
- API Inventory;
- documentation.

### 6.3 Canonical API snapshot

Normalized internal representation produced from the executable source set.

### 6.4 Build

Immutable compilation attempt from exact source versions to an MCP artifact.

### 6.5 Validation report

Machine-readable and human-readable evidence of coverage, structural correctness, semantic quality, and runtime compatibility.

### 6.6 Deployment

Running instance of a successful Build at a project-specific MCP hostname.

### 6.7 MCP access configuration

Controls authentication from external MCP consumers to the generated endpoint.

---

## 7. Primary user journeys

## UJ-01 — First installation

1. Operator runs the documented Docker Compose installation.
2. Required services become healthy.
3. Operator creates the first administrator through the secure bootstrap process.
4. Administrator logs into the UI.
5. Administrator saves or rotates the write-only OpenRouter API key in **Settings > Providers**,
   verifies live provider reachability, and selects compatible analysis, validation, and embedding
   models in **Settings > Models**.
6. Administrator configures the MCP base domain/TLS/deployment settings.
7. System reports readiness to create a project.

**Outcome:** Builder Plane ready.

## UJ-02 — Create first MCP project

1. User selects `New Project`.
2. Provides project name and slug.
3. Supplies at least one OpenAPI 3.x or API Inventory v1 source.
4. Optionally supplies documentation.
5. Chooses/configures source API base server.
6. Configures required upstream authentication.
7. Starts build.
8. System parses, indexes, analyzes, compiles, validates, and packages.
9. User sees operation coverage and findings.
10. If Build is READY, user configures MCP inbound access and deploys.
11. System displays endpoint and deployment health.

**Outcome:** External MCP client can connect.

## UJ-03 — Source has incomplete descriptions

1. OpenAPI contains structurally valid endpoints but weak summaries/descriptions.
2. Supplemental documentation contains business meaning.
3. Platform indexes documentation in Milvus.
4. OpenRouter retrieves relevant context and generates structured semantic enrichment.
5. Build produces improved MCP tool descriptions while preserving source method/path/schema exactly.
6. Validation reports provenance and any low-confidence semantic warnings.

**Outcome:** Better agent-facing semantics without invented API behavior.

## UJ-04 — Unsupported operation

1. Source contains an operation whose executable behavior cannot be represented safely by the current compiler/runtime.
2. Build reports a blocking finding for that operation.
3. User may correct source/configuration or explicitly exclude the operation.
4. Exclusion reason appears in validation report.
5. Expected-operation coverage is recalculated transparently.

**Outcome:** No silent omission and no hallucinated workaround.

## UJ-05 — API changes

1. User uploads/refreshes a new source version.
2. Platform computes differences from previous READY Build.
3. New Build analyzes affected material, recompiles full current manifest, and validates.
4. UI displays added/removed/changed/unchanged operations and documentation changes.
5. Existing deployment continues serving the previous healthy Build until the user deploys the new one.

**Outcome:** Controlled update.

## UJ-06 — Manual review/enhancement

1. User selects `Review` even when sources have not changed.
2. Platform creates a new Build with current sources.
3. Semantic analysis/review runs using current approved model/prompt configuration.
4. Structural mappings remain deterministic.
5. User compares the resulting build before deployment.

**Outcome:** Explicit AI-assisted enhancement without background continuous AI use.

## UJ-07 — Rollback

1. Newly deployed Build proves unsuitable or unhealthy.
2. Admin selects a previous READY Build.
3. Platform deploys a new runtime instance using that immutable Build.
4. Health check passes before traffic switches where supported.

**Outcome:** Previous known-good MCP behavior restored.

## UJ-08 — Export MCP bundle

1. User selects export on a READY Build.
2. Platform produces an artifact containing the project manifest/configuration/readme metadata necessary to run with the compatible generic runtime.
3. Artifact contains no plaintext credentials.

**Outcome:** Company can run generated MCP outside the Builder Plane if desired.

---

## 8. Functional requirements

Requirements are normative. IDs must be referenced by implementation/tests where useful.

### Project management

**FR-PROJ-001** — The platform shall create, list, view, update, enable/disable, and delete Projects.

**FR-PROJ-002** — Project slugs shall be unique and valid for the configured MCP hostname convention.

**FR-PROJ-003** — Project deletion shall not silently orphan an active runtime; active deployment must be stopped/removed through the controlled deletion flow.

**FR-PROJ-004** — The platform shall support multiple Projects in one installation without tenant/organization segmentation.

**FR-PROJ-005** — Every deployed Project shall have a distinct MCP hostname.

### Source ingestion

**FR-SRC-001** — A deployable Project shall require at least one executable source: OpenAPI 3.0.x/3.1.x or API Inventory v1.

**FR-SRC-002** — The platform shall accept executable sources as uploaded JSON/YAML files.

**FR-SRC-003** — The platform shall accept executable sources from administrator-provided URLs using the secure fetch subsystem.

**FR-SRC-004** — The platform shall accept supplemental JSON, Markdown, text, CSV, XLSX, DOCX, HTML, and text-extractable PDF documentation.

**FR-SRC-005** — Every source update shall create an immutable source version identified by a content hash.

**FR-SRC-006** — Remote source refresh shall create a new version only when content changes.

**FR-SRC-007** — The platform shall show parse/validation errors with source location information where available.

**FR-SRC-008** — Documentation alone shall not produce executable tools.

**FR-SRC-009** — Each logical source shall have one explicit transactionally selected immutable
current version. Reaccepting historical bytes shall reselect that version and update observation
validators without rewriting immutable version history.

### OpenAPI/API normalization

**FR-NORM-001** — The platform shall validate supported source specifications before compilation.

**FR-NORM-002** — It shall resolve supported `$ref` relationships safely and report unresolved executable references as blocking.

**FR-NORM-003** — It shall normalize all executable source formats into one versioned canonical API model.

**FR-NORM-004** — Canonical executable fields shall retain source provenance.

**FR-NORM-005** — Multiple inherited/root source servers shall require an explicit deployment server selection/mapping. Explicit path- or operation-scoped servers shall remain attached to their operations, and downstream MCP callers shall not choose arbitrary base URLs.

### Documentation/Milvus

**FR-VEC-001** — Supplemental documentation and relevant source semantics shall be chunked, embedded, and indexed in Milvus for semantic retrieval.

**FR-VEC-002** — Vector searches shall be strictly scoped by Project and index generation.

**FR-VEC-003** — Milvus state shall be rebuildable from immutable source material and embedding configuration.

**FR-VEC-004** — The system shall record embedding model and dimensions per index generation.

**FR-VEC-005** — Vector row identity and cleanup shall remain isolated across Project, generation,
source binding, and reclaimed Build execution attempt while content-based embedding reuse remains
project scoped.

### OpenRouter build intelligence

**FR-AI-001** — OpenRouter shall be configurable once at the installation level with analysis, semantic-validation, and embedding models.

**FR-AI-002** — OpenRouter shall be used only for build/index/review tasks, not runtime MCP execution.

**FR-AI-003** — AI calls affecting stored build output shall use schema-constrained structured responses where supported and always be validated into typed models.

**FR-AI-004** — AI may enrich descriptions, titles, categories, relationships, terminology, documentation correlations, and semantic findings.

**FR-AI-005** — AI shall not invent or alter executable HTTP method, host, path, parameter requirement/location/type, request schema, response schema, authentication mechanism, or secret.

**FR-AI-006** — The platform shall record model/prompt/version/context metadata sufficient to audit/reproduce build decisions without storing hidden model reasoning.

**FR-AI-007** — The user shall be able to explicitly request review/rebuild later; the product shall not continuously spend model tokens on deployed Projects.

**FR-AI-008** — The platform shall display build-time AI usage/cost metadata when OpenRouter returns it, for operator visibility only; this is not end-user billing/metering.

**FR-AI-009** — A structured AI response shall be validated before success/cache publication, and
usage/cost evidence shall include every accepted, rejected, and failed attempt exactly once.

### Compilation

**FR-COMP-001** — MCP output shall be compiled from the canonical API representation, never directly from arbitrary AI prose.

**FR-COMP-002** — Identical canonical executable input, compiler version, and configuration shall produce deterministic executable manifest structure.

**FR-COMP-003** — The product shall generate versioned `mcp-manifest/v1` artifacts.

**FR-COMP-004** — Every generated tool shall have a stable name, description, input schema, operation identity, request mapping, and auth-profile mapping.

**FR-COMP-005** — Tool arguments shall never include arbitrary upstream URL/host fields unless the source operation explicitly defines such a business parameter and it is not used as the transport destination.

**FR-COMP-006** — Target API credentials shall never be included in tool schemas or generated manifest plaintext.

**FR-COMP-007** — Supplemental documentation may compile into MCP resources with source provenance.

**FR-COMP-008** — The compiler shall not generate a separately maintained Python codebase for each Project.

### Validation

**FR-VAL-001** — Every Build shall have a validation report before becoming deployable.

**FR-VAL-002** — The report shall show source operations, explicit exclusions, expected operations, generated tools, and coverage percentage.

**FR-VAL-003** — Expected operation coverage must be 100% for a READY Build.

**FR-VAL-004** — No source operation may disappear silently.

**FR-VAL-005** — Validation shall detect dropped required parameters, duplicate tool names, invalid schemas, missing auth mapping, invalid upstream hosts, and runtime/manifest incompatibility.

**FR-VAL-006** — Validation shall start the production generic-runtime factory for the exact
candidate manifest and use an official MCP client to initialize, list tools/resources, and
successfully call every enabled tool with schema-valid representative arguments and a
schema-valid successful response. An MCP error result or inability to construct a successful
probe is blocking.

**FR-VAL-007** — Semantic AI validation findings shall not override failing deterministic validation.

### Builds/versioning

**FR-BUILD-001** — Builds shall be immutable and sequentially identifiable per Project.

**FR-BUILD-002** — A Build shall bind exact source versions.

**FR-BUILD-003** — A failed/cancelled Build shall not replace the active Build/deployment.

**FR-BUILD-004** — Build progress shall be observable by stage.

**FR-BUILD-005** — Source-change Builds shall expose operation/schema/document diffs against the prior READY Build.

**FR-BUILD-006** — Manual review and manual rebuild shall create new Builds rather than mutating existing ones.

**FR-BUILD-007** — READY Builds shall be exportable without plaintext secrets.

**FR-BUILD-008** — A Build shall freeze every executable source role/name/alias/routing input used
for parsing and identity; historical inputs that cannot be established safely shall require a new
Build before activation.

**FR-BUILD-009** — Reclaimable Build execution shall use a database lease and exact execution token
on every accepted state/result publication. Cancellation shall be acknowledged by the live owner or
recovered after owner expiry without executing another stage.

### Deployment

**FR-DEP-001** — The base platform shall deploy through Docker Compose.

**FR-DEP-002** — The deployment subsystem shall create project MCP runtimes dynamically using Docker Engine rather than statically adding every Project to the base Compose file.

**FR-DEP-003** — Each Project runtime shall be a separate hardened container using the generic MCP runtime image.

**FR-DEP-004** — Traefik shall route the configured project hostname to the correct runtime using explicit labels.

**FR-DEP-005** — Sensitive data shall not be placed in Traefik/Docker labels.

**FR-DEP-006** — Deployment shall verify runtime health before making a replacement authoritative where operationally possible.

**FR-DEP-007** — The platform shall support stop, restart, redeploy, and rollback.

**FR-DEP-008** — The web/API container shall not need direct Docker socket access; deployment authority belongs to the worker/runtime-manager path.

**FR-DEP-009** — Runtime containers shall not have access to builder PostgreSQL, Redis, Milvus, or Docker socket.

**FR-DEP-010** — Runtime commands shall be ordered, database-time leased, exact-token fenced, and
serialized per Project around Docker effects; an expired owner shall not finalize or target a
replacement container.

**FR-DEP-011** — Authentication-only maintenance shall remain bound to the exact active Build and
may bypass only unrelated source drift. Removing the final valid inbound verifier shall commit a
durable runtime stop without manufacturing an invalid replacement.

### MCP serving

**FR-MCP-001** — Generated runtimes shall serve MCP using Streamable HTTP at `/mcp`.

**FR-MCP-002** — They shall expose generated tools using exact manifest JSON Schemas.

**FR-MCP-003** — They shall expose generated documentation resources when present.

**FR-MCP-004** — On a valid external MCP tool call, the runtime shall deterministically build the configured upstream request and invoke the source product API.

**FR-MCP-005** — Runtime execution shall not call OpenRouter or Milvus.

**FR-MCP-006** — Runtime shall enforce upstream host allowlisting and must not let caller arguments override destination host/authentication.

**FR-MCP-007** — Runtime shall enforce timeouts and maximum response sizes.

**FR-MCP-008** — Runtime errors shall be returned in MCP-readable form without secrets/internal traces.

### Authentication and credentials

**FR-SEC-001** — The Builder Plane shall require authenticated local users; no public registration.

**FR-SEC-002** — Roles shall include Admin and Builder as specified by `design_document.md`.

**FR-SEC-003** — Product API credentials shall be encrypted at rest and never redisplayed in plaintext after creation/rotation. Secret rotation shall preserve the validated source-security binding; remapping scheme identity/location requires a replacement credential and a new immutable Build.

**FR-SEC-004** — MCP inbound authentication and product API outbound authentication shall be separate configurations.

**FR-SEC-005** — Production MCP endpoints shall require authentication by default.

**FR-SEC-006** — Static high-entropy bearer tokens shall be supported for MCP inbound access.

**FR-SEC-007** — External OAuth/OIDC verification may be configured as a supported advanced inbound mode.

**FR-SEC-008** — Upstream authentication shall support bearer, API key header/query, Basic, OAuth client credentials, and explicitly configured static secret headers.

**FR-SEC-009** — Secrets shall not be included in exported artifacts or routine logs.

**FR-SEC-010** — Control-plane encryption rotation shall support an active write key plus explicit
prior read keys and a transactional re-encryption operation; unknown versions shall fail closed.

### UI/administration

**FR-UI-001** — The application shall use a responsive React/Tailwind/shadcn administrative UI.

**FR-UI-002** — It shall provide Dashboard, Projects, Builds, Deployments, Activity, and Settings areas.

**FR-UI-003** — Project pages shall provide Overview, Sources, Operations/Tools, Documentation, Builds, Validation, Deployment, Credentials, and Settings.

**FR-UI-004** — The new-project flow shall guide the user through source input, docs, API server/auth, build, validation, MCP access, and deployment.

**FR-UI-005** — Build and deployment progress shall update without requiring full-page reloads.

**FR-UI-006** — There shall be no Chat, Conversations, Agents, or approval-queue UI.

**FR-UI-007** — Management collections shall expose bounded stable pages with total counts; the UI
shall explicitly traverse pages only when a workflow requires the complete collection.

### Audit/operations

**FR-OPS-001** — Control-plane security and lifecycle changes shall create durable audit events.

**FR-OPS-002** — The platform shall expose health/readiness information for base services and each deployment.

**FR-OPS-003** — Runtime logs shall be structured and sanitized.

**FR-OPS-004** — The platform shall provide documented backup/restore procedures for PostgreSQL, artifact storage, and secrets/master-key handling; Redis and Milvus shall be treated according to their authoritative/rebuildable roles.

**FR-OPS-005** — Startup and shutdown shall acquire resources transactionally and attempt every
dispatcher stop/client close within configured bounds, cancelling overdue background tasks.

**FR-OPS-006** — Production logs shall retain allowlisted lifecycle correlation fields while
omitting raw messages, exception text, query secrets, and arbitrary context.

---

## 9. Non-functional requirements

### NFR-001 — Security

Security is a release blocker. The platform must protect source documentation, credentials, generated endpoints, and the Docker host according to the controls in `architecture.md` and `design_document.md`.

### NFR-002 — Reproducibility

A Build must identify all source versions, compiler/runtime compatibility, model IDs, prompt versions, and hashes needed to understand exactly what was built.

### NFR-003 — Determinism

Executable mappings must be deterministic. AI nondeterminism may affect semantic enrichment but not silently change source API structure.

### NFR-004 — Availability isolation

Failure of OpenRouter or Milvus must not stop already deployed MCP runtimes.

### NFR-005 — Project isolation

A Project's source data, retrieval context, credentials, runtime, hostname, and logs must never be mixed with another Project's.

### NFR-006 — Performance

Builder APIs should provide normal interactive responses within reasonable web latency; long operations run asynchronously. Runtime overhead introduced by the MCP adapter should be small relative to upstream API latency and should not involve an LLM call.

Target runtime adapter overhead for normal JSON operations on a healthy host: p95 below 100 ms excluding upstream API time, under representative load and without external auth-token refresh. This is a target, not permission to sacrifice correctness/security.

### NFR-007 — Build scale

The design shall support at least:

- 100 projects in one installation;
- 1,000 operations in a single source project;
- 10,000 documentation chunks per project;

without changing architecture. Actual throughput depends on host resources and OpenRouter limits.
The documentation-chunk target covers ingestion, indexing, and bounded retrieval. Runtime
publication remains subject to the Build-frozen exact manifest byte limit; an oversized
serialization must fail validation before `READY` rather than fail during runtime startup.

### NFR-008 — Resource bounds

All uploads, remote fetches, AI contexts, queue concurrency, runtime requests, upstream responses, and logs must have explicit configurable bounds.

### NFR-009 — Operability

All services must have health checks and documented failure/remediation behavior.

### NFR-010 — Upgradeability

Database migrations, manifest schema versions, compiler versions, and runtime compatibility must permit controlled upgrades and rollback.

### NFR-011 — Testability

External integration boundaries must be replaceable with fakes/mocks. Core compile/validation behavior must run deterministically in CI without live OpenRouter.

### NFR-012 — Accessibility

The administrative UI shall target WCAG 2.1 AA-level practical accessibility: keyboard navigation, labels, focus visibility, semantic controls, adequate contrast, and screen-reader-compatible status/error messaging.

### NFR-013 — Browser support

Support current stable Chromium, Firefox, and Safari families. No IE/legacy browser requirement.

### NFR-014 — Data privacy

OpenRouter is an external processor for source/document context used during builds. The product must clearly indicate which project material is sent to OpenRouter, let administrators choose whether documentation is included in AI analysis, and never send credentials/secrets. Users are responsible for selecting models/providers appropriate for their data policies.

### NFR-015 — No telemetry by default

The open-source installation shall not transmit product analytics/telemetry to the project maintainer by default. Any future opt-in telemetry must be explicit and documented.

---

## 10. Security/product constraints

1. The product cannot promise that every arbitrary API can be automatically represented. Unsupported operations must be reported/excluded safely.
2. API credentials are required for a deployed runtime when the source product requires authentication; the platform cannot infer credentials from documentation.
3. The platform shall not ask an AI model to execute or test mutating product API calls during build.
4. Remote source fetching can reach only allowed destinations.
5. A deployment whose runtime manifest or secrets fail validation must remain unavailable/unhealthy.
6. Internet-exposed MCP endpoints must not default to anonymous access.
7. Company documents passed through OpenRouter are sent only as bounded relevant context; secret fields are excluded.

---

## 11. Product constraints inherited from open-source model

The product itself shall contain no functionality whose purpose is to enforce sponsorship/commercial payment.

Specifically no:

- subscription plans;
- license-key entitlement server;
- paid-feature checks;
- sponsor-only capabilities;
- usage-based customer billing;
- cloud account tenancy;
- hosted-service assumptions.

Professional services/support/sponsorship exist outside runtime product behavior and are governed by `open_source_and_sponsorship_model.md`.

---

## 12. Explicit out of scope

The following are not part of the product unless a later authoritative revision says otherwise:

### AI/chat

- built-in user chat;
- conversation history;
- model chat UI;
- agent loop;
- agent memory;
- autonomous business operation execution by the Builder Plane;
- human approval/HITL for runtime tool calls.

### SaaS/business billing

- multi-tenancy;
- customer organizations/workspaces as tenancy boundaries;
- subscriptions;
- billing plans;
- payment gateways;
- seat licensing;
- quotas/entitlements;
- sponsor authentication into software features.

### Infrastructure complexity

- Kubernetes required deployment;
- microservices required deployment;
- Kafka/RabbitMQ;
- service mesh;
- separate vector DB other than Milvus;
- pgvector.

### Generation model

- arbitrary per-project Python MCP application generation;
- generated executable code based solely on LLM output;
- executable endpoints inferred from documentation alone.

### API format scope

- Swagger/OpenAPI 2.0 native ingestion in core V1;
- GraphQL introspection-to-MCP compiler;
- gRPC/protobuf-to-MCP compiler;
- SOAP/WSDL-to-MCP compiler;
- arbitrary browser/UI automation.

These may become future adapters but must use the same canonical/compiler architecture.

### Document understanding

- OCR for image-only documents in core V1;
- audio/video transcription;
- arbitrary proprietary documentation-system connectors.

---

## 13. UX requirements

### 13.1 Clarity over magic

The UI shall always show what source operations were discovered, what tools were generated, what was excluded, and why. “AI generated successfully” is not sufficient evidence.

### 13.2 Source vs enrichment visibility

Users should be able to distinguish source-derived structure from AI-enriched descriptions/findings.

### 13.3 Progressive disclosure

Default project overview should show status/coverage/endpoint. Detailed schemas/provenance/logs are available in deeper views.

### 13.4 Safe secret UX

Secret forms:

- never display saved secret values;
- clearly show `configured`, `rotated at`, and non-secret prefix/name;
- rotate rather than reveal;
- require confirmation for revocation affecting active deployment.

### 13.5 Action states

Buttons must respect lifecycle:

- Deploy disabled until Build READY and required auth configured;
- Rebuild allowed from Project even if previous deployment exists;
- Delete blocked/explicit when active resources exist;
- Rollback targets READY historical Builds only.

---

## 14. Product acceptance scenarios

### AC-001 — Two independent APIs

Given two valid OpenAPI specifications for different products, when both are built and deployed, then:

- both validation reports pass;
- both use the same generic runtime image family;
- each exposes its own tools;
- each has a different hostname and secret set;
- one runtime cannot access the other's project data;
- stopping one does not stop the other.

### AC-002 — Documentation enrichment does not change execution

Given a source operation `GET /customers/{id}` and documentation that describes customers, when AI enrichment runs, then:

- title/description may improve;
- method/path/required `id` remain source-identical;
- build provenance shows source + enrichment separately.

### AC-003 — Hallucination resistance

Given documentation that mentions a capability absent from OpenAPI/API Inventory, when building, then no executable MCP tool for that capability is generated.

### AC-004 — Invalid source

Given an unresolved executable `$ref`, when building, then Build becomes FAILED or the specific operation is a blocking finding until explicitly excluded/corrected; Build cannot silently become READY with that operation missing.

### AC-005 — Runtime independence

Given a healthy deployed Project, when OpenRouter/Milvus/control-plane worker are unavailable, then external MCP clients can still call the runtime and reach the upstream API, provided Docker/Traefik/runtime/upstream API remain healthy.

### AC-006 — No HITL

Given an external MCP client makes a valid call to a generated write/delete API tool and it is authenticated, then the MCP runtime executes the deterministic mapping without creating a platform approval request.

### AC-007 — No chat

A production UI/API inspection shall find no chat/conversation/agent-loop product capability.

### AC-008 — Secure destination

Given tool arguments containing values resembling URLs/internal metadata IPs, when the tool mapping does not define those values as the transport destination, then the caller cannot change the runtime's upstream host.

### AC-009 — Rebuild safety

Given Build 5 is deployed and Build 6 fails validation, then Build 5 remains the active healthy deployment.

### AC-010 — Rollback

Given Builds 5 and 6 are READY and 6 is active, when rollback to 5 is requested, then a deployment using Build 5 is started/health-checked and becomes active without mutating either Build.

### AC-011 — Secret protection

Exports, manifests, API responses, audit events, and normal logs must contain no plaintext upstream credential or MCP access token.

### AC-012 — Full expected coverage

Given 100 source operations and 4 explicit exclusions, a READY Build must contain 96 generated expected tools (subject only to documented many-to-one compiler rules, if any are later introduced) and report 100% expected coverage.

---

## 15. Release criteria for initial stable release

A release may be called initial stable only when:

1. Docker Compose installation and upgrade path are documented and reproducible.
2. OpenAPI 3.0/3.1 JSON/YAML and API Inventory v1 imports pass representative fixture suites.
3. Documentation indexing in Milvus and OpenRouter semantic enrichment are functional and securely bounded.
4. At least all required V1 upstream auth types are implemented and tested.
5. Compiler/manifest/runtime contracts are versioned and tested.
6. Protocol tests prove external MCP clients can list/call tools over Streamable HTTP.
7. Per-project deployment/subdomain routing works through Traefik.
8. Static bearer MCP access authentication works and production anonymous mode is disabled by default.
9. Validation reports prove expected operation coverage and explicit exclusions.
10. Build diff/review/rebuild/rollback flows are implemented.
11. Secrets are encrypted/redacted and security tests pass.
12. No chat, HITL, SaaS tenancy, subscription, sponsor entitlement, or pgvector implementation exists.
13. CI passes backend, runtime, frontend, integration, security, and E2E suites.
14. Open-source release/governance files required by `open_source_and_sponsorship_model.md` are present and enforced.
15. The implementation has no known repository-controlled blocker against the requirements in this documentation set.
