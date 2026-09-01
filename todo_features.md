# MCPlica — Business Feature Backlog

**Repository:** `yazeedhasan97/MCPlica`  
**Branch reviewed:** `master`  
**Code/product baseline:** `2273e46d79104ba661f1a6efbff0951d3a9597b0`  
**Research date:** 2026-09-01  
**Status:** Proposed features; none implemented by this task.

## 1. Purpose and review boundary

This backlog identifies useful business capabilities beyond MCPlica's existing API-to-MCP conversion, build validation, credential management, and isolated deployment functionality. It combines a renewed review of product requirements and relevant implementation boundaries with first-party research into nine competing/adjacent platforms and three companies publishing their own MCP servers.

This is a product/capability review, not a completed every-file audit, penetration test, customer-demand survey, or comparative performance benchmark. “New” means not present in the reviewed canonical product surface; “Extend” identifies an existing capability with a specific additional outcome. Recheck implementation status before starting each feature. Vendor documentation establishes advertised behavior, not independent proof of quality, availability, or superiority. Business benefits are proposed outcomes to measure, not guaranteed savings.

Existing defects remain in [issues_002.md](issues_002.md). Do not disguise their correction as new functionality or assume they have been resolved.

## 2. Existing strengths to preserve

MCPlica already specifies or implements OpenAPI 3.0/3.1 and API Inventory ingestion; source versioning; documentation enrichment; deterministic manifests; structural/protocol validation; build diffs; credential encryption; static bearer and external OIDC runtime authentication; per-project Docker runtimes; rollback; and secret-free exports. Basic versions of those capabilities are **not** new backlog items. [R1–R6]

The intended product remains self-hosted and fully open source, with one installation containing many projects, one isolated runtime/subdomain per project, and no SaaS tenancy or billing. OpenRouter and Milvus stay on the build side. The external company-owned agent decides what business operation to call; MCPlica does not become that agent. [R1–R3]

### Implementation constraints applying to every feature

- Enhance the existing FastAPI services/repositories, shared contracts, React control plane, dedicated clients, and generic runtime. Preserve PostgreSQL as authoritative state and existing queue/storage boundaries.
- Do not introduce V2 implementations, duplicate services/persistence, parallel serving paths, staging-specific behavior, shadow/canary flows, approval workflows, authority gates, or a replacement architecture.
- Ordinary automatic authentication and permission enforcement remain necessary. Authorized calls execute without a new human-approval step. Client-supplied preferences may narrow access, never grant it.
- Do not add runtime LLM calls, runtime Milvus dependencies, arbitrary code execution, or mandatory Builder Plane round trips on each tool call. Optional telemetry must not become a serving dependency.
- Freeze executable changes in the canonical build artifacts; keep mutable access/secret state in the established deployment-overlay lifecycle. Extend contracts and their compatibility checks together, without maintaining a second implementation.
- Do not add subscriptions, feature entitlements, customer billing, or commercial quotas. Resource limits below protect infrastructure; usage reporting is operational visibility only.
- Use focused TDD/BDD, negative authorization cases, and cross-component tests. Do not add test execution to deployment. Update authoritative specifications during later feature implementation; this backlog alone does not rewrite them.

## 3. Competitive and practitioner comparison

These products address overlapping but different needs. An API compiler, MCP framework, connector service, and enterprise gateway are not interchangeable.

| Platform / project | Relationship to MCPlica | Relevant documented capability | Transferable opportunity, without copying its architecture |
| --- | --- | --- | --- |
| **Speakeasy** | Direct API-to-MCP generation overlap | Standalone generation and configurable tool names, descriptions, scopes, and annotations. [C1, C2] | Business-oriented tool curation and easier distribution; preserve MCPlica's generic manifest runtime. |
| **Stainless** | Direct generation overlap, different execution model | OpenAPI/SDK-based MCP generation; current documentation uses code mode with documentation search, and describes generation as experimental. OAuth configuration is documented. [C3, C4] | Reduce catalog/context overhead and simplify authentication. Do not adopt executable agent-generated code. |
| **FastMCP** | Open-source framework / developer-built alternative | OpenAPI integration, tool transformations, and bounded on-demand search with authorization-aware visibility. [C5, C6] | Curated tools and local discovery. Do not replace the current MCP SDK/runtime with a second framework. |
| **IBM ContextForge** | Self-hosted gateway/registry alternative | Federation, registry management, rate limiting, retries, audit metadata, and OpenTelemetry. [C7] | Operational visibility, private catalog distribution, and traffic protection; not federation or agent routing. |
| **AWS AgentCore Gateway** | Managed enterprise alternative | OpenAPI targets, semantic tool search, and outbound OAuth/API-key/IAM authentication. [C8, C9] | Enterprise identity and discovery without requiring AWS hosting or its gateway architecture. |
| **Azure API Management** | Enterprise API gateway alternative | Exposes managed REST operations as MCP tools and supports policy-based management and programmatic configuration. [C10] | Headless lifecycle management and fit with existing enterprise API operations. |
| **Composio** | Managed application-connection alternative | User-scoped sessions, tool discovery, connected accounts, and managed authentication. [C11] | Named consumers, least-privilege discovery, and carefully scoped delegated identity—not SaaS tenancy. |
| **Arcade** | Tool/authentication and gateway alternative | Curated tool collections and endpoint instructions; operational setup includes end-user identity and audit logging. [C12, C13] | Application-specific tool collections and auditable identity-bound execution; no multi-project proxy. |
| **Pipedream Connect/MCP** | Managed prebuilt-integration alternative | App-specific tools, managed OAuth, credential isolation, and client onboarding. [C14] | Reusable configuration recipes and simpler connection setup; not a competing general-purpose iPaaS. |
| **GitHub MCP Server** | API owner publishing its own MCP | Configurable toolsets, individual tool selection, scope filtering, and read-only behavior. [C15] | Department/application tool profiles with server-enforced restrictions. |
| **Atlassian Rovo MCP** | Enterprise API owner publishing its own MCP | OAuth/API-token options and actions constrained by the authenticated user's existing permissions. [C16] | Preserve upstream user permissions rather than execute every consumer through a broad shared credential. |
| **Stripe MCP** | API owner publishing its own MCP | API-method search/details, documentation search, client installation guidance, and scoped session management. [C17] | Searchable capability onboarding and per-consumer administration—not payment functionality inside MCPlica. |

### Implications for MCPlica

The comparison supports four product directions: **make tools easier to discover and use; make access attributable and least-privilege; automate API lifecycle work; and provide enterprise operational evidence**. These are analysis conclusions from the capabilities above, not market-share or customer-demand claims.

MCPlica can pursue them while preserving its existing differentiators: source-faithful compilation, explicit provenance, independently usable runtimes, and company-controlled hosting. Competing on the number of hosted SaaS integrations or on arbitrary code execution would move away from that product definition. [R1–R3]

## 4. Priorities and sizing

**P1 — Enterprise adoption foundations:** broad applicability, safer access, and lower onboarding/operating friction.  
**P2 — Workflow depth and integration value:** build on the foundations or address a more specific enterprise need.  
**P3 — Targeted differentiation:** valuable when confirmed by an actual customer workflow; not required for every installation.

**Effort:** S = a relatively bounded extension; M = coordinated changes across several existing components; L = substantial identity, contract, or execution-boundary work. These are comparative planning judgments, not delivery-time or cost estimates. Dependencies can change implementation order within a priority.

| ID | Feature | Priority | Effort |
| --- | --- | --- | --- |
| F-001 | Tool-level permissions and read-only consumer profiles | P1 | L |
| F-002 | Named consumer applications and access lifecycle | P1 | M |
| F-003 | Control-plane SSO and identity-provider MFA integration | P1 | M |
| F-004 | Project-scoped collaboration and read-only audit access | P1 | L |
| F-005 | Runtime observability and operational service dashboards | P1 | M |
| F-006 | Runtime invocation audit and SIEM export | P1 | M |
| F-007 | Business-oriented tool curation and annotations | P1 | M |
| F-008 | Bounded, permission-aware runtime tool discovery | P1 | M |
| F-009 | Consumer connection center and client configuration export | P1 | S |
| F-010 | Service-account automation, CLI, and configuration as code | P1 | L |
| F-011 | Opt-in Git/source synchronization and rebuild automation | P1 | M |
| F-012 | Operational rate limits, concurrency controls, and circuit breaking | P1 | M |
| F-013 | Upstream delegated identity through token exchange | P2 | L |
| F-014 | Enterprise secrets-manager integration | P2 | M |
| F-015 | Enterprise upstream authentication profiles | P2 | L |
| F-016 | Field-level data minimization and constrained business inputs | P2 | L |
| F-017 | Source-declared pagination and bounded collection retrieval | P2 | M |
| F-018 | Binary attachments and report-download support | P2 | L |
| F-019 | Source-aware idempotency and actionable error recovery | P2 | M |
| F-020 | Source-defined long-running operation support | P2 | L |
| F-021 | Consumer impact analysis and deprecation tracking | P2 | M |
| F-022 | Business-scenario and tool-discoverability evaluation | P2 | M |
| F-023 | Non-chat API/MCP contract playground | P2 | M |
| F-024 | Private capability catalog and registry-compatible metadata | P2 | M |
| F-025 | Lifecycle notifications and operational integrations | P2 | M |
| F-026 | Automated backup, restore, and project migration utilities | P2 | M |
| F-027 | Searchable, portable documentation resource bundles | P3 | M |
| F-028 | Reusable business API configuration blueprints | P3 | M |
| F-029 | Explicitly compiled, single-project business task tools | P3 | L |
| F-030 | Signed project-artifact distribution and verification | P3 | M |
| F-031 | Build-data privacy controls and processing visibility | P2 | M |
| F-032 | Multilingual business terminology and tool documentation | P3 | M |

**Total: 32 features — 12 P1, 15 P2, 5 P3.** Every entry remains unchecked because this task is documentation only.

## 5. Detailed feature backlog

### [ ] F-001 — Tool-level permissions and read-only consumer profiles

**Priority / effort:** P1 / L. **Type:** Extend runtime authentication. **Dependencies:** F-002; correct the relevant access/lifecycle findings in `issues_002.md`.

**Business value:** Let a reporting assistant read inventory while a support application can update support records, without giving both every operation in the project.

**Current delta:** Runtime authentication exists, but `build_server()` discards request context and lists the manifest tool set. Static token verification returns empty scopes; the reviewed tool contract has no per-consumer permission policy. [R4–R6]

**Deliver:** Bind named consumers and trusted identity claims to explicit operation/resource sets; provide read-only and business-function presets. Apply identical checks to listing, search, resource reads, and execution. Deny wins; unknown tools and spoofed claims cannot broaden access. Keep one project endpoint/runtime. Publish access changes through the existing overlay lifecycle and distinguish requested from effective revocation. Read-only classification must use explicit source/operator evidence, not HTTP method alone.

**Acceptance:** Two consumers see/call only their permitted tools; direct calls to hidden unauthorized tools fail; search leaks no restricted schemas; a read-only consumer cannot mutate; an applied revocation removes access while unrelated consumers continue. **Relevant precedent:** GitHub toolsets and scope filtering; Composio session scoping. [C15, C11]

### [ ] F-002 — Named consumer applications and access lifecycle

**Priority / effort:** P1 / M. **Type:** Extend MCP access administration.

**Business value:** Identify which internal assistant, integration, or unattended job owns each connection and stop sharing anonymous team-wide tokens.

**Current delta:** Access tokens and OIDC client identifiers exist, but they are not a complete application inventory with ownership, purpose, contact, granted capabilities, and connection health. [R5, R7]

**Deliver:** Add consumer metadata and bindings within the existing project/access model: owner, purpose, application identifier, credential references, expiry, last-observed activity, permitted profile, and revocation state. Show rotation history and stale consumers; keep plaintext issuance one-time. Treat runtime end users as external identities, not new SaaS tenants or paid seats. Distinguish observed activity from an inferred active session.

**Acceptance:** Create two applications, rotate/revoke one without affecting the other, verify ownership/audit attribution and secret-free exports, and show last activity only from actual observations. **Relevant precedent:** Stripe session administration and Composio connected identity. [C17, C11]

### [ ] F-003 — Control-plane SSO and identity-provider MFA integration

**Priority / effort:** P1 / M. **Type:** New control-plane login integration; not a duplicate of inbound runtime OIDC.

**Business value:** Use the company's identity lifecycle and MFA rather than separately maintaining every administrator's password.

**Current delta:** The reviewed control-plane identity model has local users and admin/builder roles; runtime OIDC solves a different boundary. [R5, R8]

**Deliver:** Integrate an explicitly configured corporate OIDC provider, mapping immutable issuer/subject pairs to existing user records. Let the IdP enforce MFA; consume assurance claims only under a validated provider policy. Support deliberate account linking, session termination, deactivation, and an audited local recovery administrator. Never link solely by an unverified email or trust arbitrary group claims.

**Acceptance:** Successful login, invalid issuer/audience, expired tokens, disabled users, changed group assignments, logout, and safe recovery during IdP outage. Existing users and audit identities remain coherent. **Relevant precedent:** Arcade's enterprise identity setup. [C13]

### [ ] F-004 — Project-scoped collaboration and read-only audit access

**Priority / effort:** P1 / L. **Type:** Extend installation authorization. **Dependencies:** Reuse F-003 identity mappings when SSO is configured.

**Business value:** Different teams can manage their own products in one company installation; auditors can inspect evidence without acquiring deployment or secret-management powers.

**Current delta:** Admin/builder roles are installation-level; project records already provide the natural permission boundary. [R2, R8, R9]

**Deliver:** Add project membership and explicit capabilities for view, source editing, building, deployment, credential administration, and audit reading. Map trusted IdP groups to those memberships where configured. Centralize checks in current dependencies/services and apply them to exports, event streams, metadata, and background-request ownership. Do not introduce organizations/workspaces as tenancy boundaries or approval chains.

**Acceptance:** A user from team A cannot enumerate or mutate team B's project through any endpoint; a viewer can inspect but cannot build/deploy; group removal takes effect within the defined session policy. **Relevant precedent:** Enterprise access-control patterns in Arcade and Azure API Management. [C13, C10]

### [ ] F-005 — Runtime observability and operational service dashboards

**Priority / effort:** P1 / M. **Type:** Extend existing health/logging into runtime operations analytics.

**Business value:** Operations teams can distinguish MCP adapter failures from upstream API, authentication, and capacity problems.

**Current delta:** Health endpoints and sanitized failure logs exist. The reviewed runtime is not a full per-tool, per-consumer latency/error dashboard. [R4, R10]

**Deliver:** Capture request counts, successful outcomes, error categories, duration distributions, in-flight calls, response sizes, and version/build identifiers. Add optional OpenTelemetry export to a company-controlled collector and dashboards for adapter versus upstream latency. Bound label cardinality and buffers; do not log bodies or transmit maintainer telemetry. Export failure must not interrupt normal serving.

**Acceptance:** Known success/timeout/auth failures produce correct counters and traces; p95 is computed from an actual distribution; collector outage leaves runtime calls available; metrics expose no secrets or unbounded identifiers. **Relevant precedent:** ContextForge OpenTelemetry and observability. [C7]

### [ ] F-006 — Runtime invocation audit and SIEM export

**Priority / effort:** P1 / M. **Type:** Extend platform-change auditing to business invocation evidence. **Dependencies:** F-002; share instrumentation with F-005.

**Business value:** Security teams can determine which authenticated application/user called which business capability and what outcome was observed.

**Current delta:** Control-plane audit history and runtime error logging are not equivalent to a complete invocation record. [R1, R4, R7]

**Deliver:** Define a safe event schema containing consumer/subject identifiers, operation, project/build, timestamp, correlation ID, authorization result, and observed outcome. Export through a dedicated client to the company's log/SIEM destination. Provide retention controls, bounded buffering, delivery-gap reporting, and export integrity metadata. Payload capture stays off by default; no hidden model reasoning or token plaintext. Do not claim lossless auditing during unlimited outages.

**Acceptance:** Trace allowed and denied calls end to end; prove sensitive payloads are excluded; simulate exporter failure and recovery; distinguish delivered, buffered, and lost events. **Relevant precedent:** Arcade audit-enabled operations and ContextForge audit metadata. [C13, C7]

### [ ] F-007 — Business-oriented tool curation and annotations

**Priority / effort:** P1 / M. **Type:** Extend AI enrichment with deterministic operator-controlled curation.

**Business value:** Replace ambiguous API terminology with clear business descriptions, examples, and usage guidance while preserving the actual API contract.

**Current delta:** Tools have names, descriptions, schemas, and provenance, but the reviewed manifest does not carry standard behavioral annotations or a complete curation policy. [R3, R6]

**Deliver:** Add versioned per-operation titles, descriptions, examples, business categories, and supported MCP annotations. Preserve stable tool identifiers, source lineage, and schema-valid examples. Lock operator-authored semantics against accidental AI overwrite. Behavioral hints are not authorization controls; do not infer financial/destructive safety solely from verbs. Freeze curation in the build and expose the semantic diff.

**Acceptance:** Rebuilds retain deliberate overrides; mappings remain identical; examples validate; annotation changes are visible; renamed tools appear as explicit breaking changes rather than silent compatibility aliases. **Relevant precedent:** Speakeasy customization and FastMCP transformations. [C2, C5]

### [ ] F-008 — Bounded, permission-aware runtime tool discovery

**Priority / effort:** P1 / M. **Type:** Extend paginated catalog listing. **Dependencies:** F-001, F-007.

**Business value:** Large APIs become usable without putting every operation schema into an agent's initial context.

**Current delta:** Runtime tool listing is paginated, but pagination alone is not relevance search or selective disclosure. [R4]

**Deliver:** Compile a compact local search index from stable tool names, descriptions, parameter names, and curated business synonyms. Provide bounded discovery/schema retrieval through ordinary, explicitly named MCP tools, not invented protocol methods. Use local lexical ranking; no runtime model or Milvus query. Apply access filters before returning results. A discovered invocation must reach the same canonical executor as a direct call; no alternative transport/execution path. Keep source-operation coverage distinct from catalog helper tools.

**Acceptance:** A 1,000-operation fixture returns bounded, relevant permitted results; exact schemas are preserved; collisions and malformed queries fail safely; discovery works with the Builder Plane offline. Measure context reduction rather than promising a percentage. **Relevant precedent:** FastMCP search and AWS tool discovery. [C6, C9]

### [ ] F-009 — Consumer connection center and client configuration export

**Priority / effort:** P1 / S. **Type:** Extend endpoint presentation. **Dependencies:** F-002.

**Business value:** Reduce the steps required to connect an internal assistant, IDE, or automation to a deployed project.

**Current delta:** Deployment/endpoint information exists; the additional deliverable is validated client-specific setup and connection diagnostics, not another deployment engine. [R1, R9]

**Deliver:** Generate configuration snippets for supported MCP clients, display the exact endpoint/authentication method, and provide copyable setup steps. Use secret references/placeholders, never saved plaintext. Add a non-mutating connection check for TLS, authentication, initialization, and bounded tool listing, with client/version compatibility notes. Do not claim universal client support from a JSON template alone.

**Acceptance:** Representative configured clients initialize and list permitted tools; expired credentials yield actionable guidance; exports contain no secrets; a diagnostic check invokes no business operation. **Relevant precedent:** Stripe and Pipedream onboarding. [C17, C14]

### [ ] F-010 — Service-account automation, CLI, and configuration as code

**Priority / effort:** P1 / L. **Type:** Extend existing REST lifecycle APIs, not create duplicate APIs. **Dependencies:** F-004 for project scope.

**Business value:** Platform teams can provision and maintain many API-to-MCP projects from existing CI/CD systems without browser automation or human passwords.

**Current delta:** The platform has REST services and developer scripts. The new capability is scoped non-human access and repeatable declarative lifecycle management. [R1–R3, R8]

**Deliver:** Add project-scoped service identities and a small CLI over existing authenticated APIs. Support validate, inspect/diff, apply configuration, import source, build, export, and explicitly requested deploy/rollback. Provide idempotency, machine-readable output, secret references, and meaningful exit codes. Declarative configuration must reconcile into current authoritative models rather than become a second database. Keep deployment separate from optional verification commands.

**Acceptance:** Reapplying unchanged configuration creates no duplicate projects/sources/builds; credentials cannot escape scope; interrupted operations resume accurately; CLI and UI show the same state. **Relevant precedent:** Azure programmatic management and Stainless generation workflows. [C10, C3]

### [ ] F-011 — Opt-in Git/source synchronization and rebuild automation

**Priority / effort:** P1 / M. **Type:** Extend manual source upload/refresh. **Dependencies:** F-010; fix source-selection and frozen-identity defects first.

**Business value:** Keep the MCP representation aligned with the API team's actual specification without repeatedly uploading the same files.

**Current delta:** URL refresh and immutable versions exist; the addition is authenticated repository synchronization and explicit update policy. [R3, R7]

**Deliver:** Configure a repository/file/ref or an allowed source URL, signed webhook or schedule, and content-change detection. Resolve each fetched revision to immutable content and capture linked dependencies consistently. Verify webhook signatures, deduplicate deliveries, bound fetches, and expose last-success/error state. Rebuild only when explicitly enabled and inputs materially change; otherwise notify. Never deploy automatically merely because a webhook arrived, and never execute fetched repository code.

**Acceptance:** Duplicate events create one update, unchanged content incurs no unnecessary AI work, A→B→A selects the correct content, credentials remain scoped, and a failed update leaves the active runtime unchanged. **Relevant precedent:** Stainless automated regeneration on specification changes. [C3]

### [ ] F-012 — Operational rate limits, concurrency controls, and circuit breaking

**Priority / effort:** P1 / M. **Type:** Extend request/response bounds. **Dependencies:** F-002, F-005.

**Business value:** An agent loop or failing upstream should not exhaust the company's API or make other authorized consumers unusable.

**Current delta:** Connection and payload limits exist; they are not per-consumer request throttling or upstream failure isolation. [R6, R10]

**Deliver:** Configure technical burst/rate limits, concurrent-call ceilings, and bounded circuit-breaking behavior per project/consumer or source-defined operation group. Return explicit retry guidance and metrics. Keep decisions local to the single runtime and publish configuration through existing mechanisms. These are infrastructure safeguards, not paid quotas or feature entitlements. Do not claim durable global limits across unsupported multi-runtime topologies.

**Acceptance:** One noisy consumer is constrained without starving another; timeout storms open/recover the circuit predictably; waiting work is bounded; no new Builder Plane dependency appears. **Relevant precedent:** ContextForge rate limiting and retry controls. [C7]

### [ ] F-013 — Upstream delegated identity through token exchange

**Priority / effort:** P2 / L. **Type:** Extend upstream authentication. **Dependencies:** F-001, F-002, F-006.

**Business value:** An HR or support assistant accesses only records its actual user is permitted to access, instead of inheriting a broad shared service account.

**Current delta:** Inbound OIDC and upstream client-credentials authentication exist, but they do not automatically propagate the caller's upstream user permissions. [R5, R6]

**Deliver:** Support explicitly configured corporate token-exchange/on-behalf-of profiles for providers that offer them. Validate the inbound token for MCPlica and obtain a separate audience-bound upstream token through the dedicated OAuth client. Bind short-lived caches to issuer, subject, consumer, audience, and scopes. Never forward the inbound MCP bearer unchanged or put user tokens in tool arguments. Use the external IdP directly for exchange, without making the Builder Plane a per-call broker. Unsupported delegation fails closed; no automatic fallback to elevated service credentials.

**Acceptance:** Users with different upstream permissions remain distinct; wrong audience/issuer and escalation attempts fail; cache entries never cross users; IdP failures produce a safe auth error. **Relevant precedent:** Atlassian user-permission preservation and AWS outbound OAuth; token separation follows MCP authorization requirements. [C16, C8, S1]

### [ ] F-014 — Enterprise secrets-manager integration

**Priority / effort:** P2 / M. **Type:** Extend encrypted credentials and secret materialization.

**Business value:** Companies can manage rotation and access centrally in their existing secrets system instead of manually copying every credential.

**Current delta:** MCPlica encrypts stored credentials and mounts runtime secret bundles. This feature adds externally managed secret references to that same lifecycle. [R1, R7]

**Deliver:** Add dedicated provider clients for a selected enterprise secrets backend, such as Vault or a cloud secrets manager, driven by an actual deployment need. Persist references/version metadata in existing credential records; resolve only at authorized materialization/rotation boundaries. Preserve the canonical secret bundle, key-version handling, expiry checks, and requested/effective lifecycle status. Do not require the runtime to contact a vault for every tool call or create a second secret repository.

**Acceptance:** Resolve and rotate a versioned secret without revealing it, reject expired/missing material, survive provider outage with truthful state, and retain project isolation. **Rationale:** Architecture-derived enterprise integration proposal; existing authentication platforms illustrate the broader credential-management need. [R2, C14]

### [ ] F-015 — Enterprise upstream authentication profiles

**Priority / effort:** P2 / L. **Type:** Extend canonical auth-profile support. **Dependencies:** F-014 when externally managed credentials are used.

**Business value:** Connect internal APIs requiring client certificates, signed cloud requests, or combinations of authentication mechanisms.

**Current delta:** The manifest supports a finite set of bearer, API-key, Basic, client-credentials, and static-header profiles, with a single security-profile reference per tool. [R6]

**Deliver:** Add customer-required mutual TLS/custom CA, AWS SigV4, and source-declared AND-combinations through the existing auth-profile/compiler/client boundaries. Implement each as an explicit supported mapping with credential provenance, short-lived material where available, header-collision checks, and clear unsupported cases. No arbitrary executable authentication scripts, unsafe TLS bypass, or inferred security alternatives.

**Acceptance:** Valid/expired certificates, incorrect signing scope, payload-signature integrity, combined required credentials, and header conflicts are covered. Missing any mandatory credential fails before the business request. **Relevant precedent:** AWS documents IAM/SigV4 outbound support; the other profile additions are targeted enterprise proposals, not claimed universal competitor features. [C8]

### [ ] F-016 — Field-level data minimization and constrained business inputs

**Priority / effort:** P2 / L. **Type:** Extend manifest-level input/output policy. **Dependencies:** F-001, F-007.

**Business value:** A support assistant can receive order status without payment details and cannot choose a different business-unit identifier through free-form arguments.

**Current delta:** Full source schemas and request mappings exist; they do not by themselves define consumer-specific field disclosure or narrower business constraints. [R4, R6, R10]

**Deliver:** Compile explicit parameter restrictions, trusted identity-bound parameter values, and response-field allowlists into typed policy. Validate source responses before applying a declared projection and publish the actual projected output schema. Preserve units and meaning; never silently fabricate/default business data. Apply restrictions before data reaches the caller, with nested/array handling and safe errors. Upstream row-level authorization must remain authoritative; client-side filtering is not a substitute.

**Acceptance:** Restricted nested fields never appear in success/errors/logs; conflicting caller input fails; allowed responses validate against the exposed schema; pagination/search cannot bypass identity restrictions. **Relevant precedent:** AWS fine-grained gateway controls; the exact deterministic projection design is MCPlica-specific. [C9]

### [ ] F-017 — Source-declared pagination and bounded collection retrieval

**Priority / effort:** P2 / M. **Type:** Extend ordinary query-parameter mappings.

**Business value:** Reporting and support applications can reliably retrieve complete bounded datasets rather than mistake the first page for all records.

**Current delta:** MCP tool-list pagination exists, and source query parameters can be mapped. Business API pagination is a separate contract. [R4, R6]

**Deliver:** Model source-declared cursor, offset, or page-number pagination, maximum records/pages, and continuation metadata. Normalize continuation handles without letting them replace the configured destination. Return one bounded page by default; any multi-page read must be explicitly modeled and capped. Clearly label partial results, remaining pages, expiry, and upstream pagination limitations. Never claim snapshot consistency that the upstream does not offer.

**Acceptance:** Empty/final pages, repeated cursors, upstream errors halfway through, changing datasets, and foreign continuation tokens produce correct bounded behavior. **Rationale:** Business usability extension to MCPlica's request contract, not a claim of a new industry-wide protocol method. [R6, R10]

### [ ] F-018 — Binary attachments and report-download support

**Priority / effort:** P2 / L. **Type:** Extend runtime response formats. **Dependencies:** F-001, F-016.

**Business value:** Existing finance, ERP, and support APIs can return invoices, spreadsheets, or attachments through MCP without embedding enormous encoded strings in model context.

**Current delta:** Multipart input mapping exists, but the reviewed API client accepts successful JSON/text bodies and rejects other content types. [R6, R10]

**Deliver:** Support explicitly declared binary responses and bounded streaming/resource delivery through the existing runtime. Include MIME type, size, checksum, filename, provenance, and access-controlled expiring references. Any temporary content is bounded disposable runtime data, not a new authoritative store. Fetch only configured source operations; do not follow arbitrary URLs found in a response. Preserve secret isolation and cleanup on disconnect/restart.

**Acceptance:** PDF/CSV/XLSX fixtures download intact; oversized bodies stop within limits; another consumer cannot fetch a private resource; expired/restarted temporary references fail explicitly. **Rationale:** Source-fidelity and business-workflow extension beyond the currently reviewed formats. [R6, R10]

### [ ] F-019 — Source-aware idempotency and actionable error recovery

**Priority / effort:** P2 / M. **Type:** Extend upstream execution/error semantics. **Dependencies:** F-005, F-006.

**Business value:** Reduce duplicate orders/tickets and unnecessary repeated tool calls when upstream requests fail or return unclear errors.

**Current delta:** Runtime errors are sanitized and requests bounded, but source-defined idempotency and useful recovery metadata are not represented in the reviewed tool contract. [R6, R10]

**Deliver:** Support declared idempotency-key headers and safe retry policies in the canonical mapping. Propagate the same key for the same logical request; never infer exactly-once behavior for an API that does not provide it. Expose allowlisted source error codes, retryability, retry-after guidance, and whether the outcome is unknown. Do not retry ambiguous writes merely because they timed out. Retain payload redaction and validate any source lookup used for reconciliation.

**Acceptance:** A lost response followed by an allowed retry does not duplicate an upstream operation that supports idempotency; unsupported writes report uncertainty; rate-limit guidance and safe error details survive normalization. **Relevant precedent:** Gateway retry functionality; MCPlica's stricter source-specific semantics remain an explicit design choice. [C7]

### [ ] F-020 — Source-defined long-running operation support

**Priority / effort:** P2 / L. **Type:** Extend deterministic execution mappings. **Dependencies:** F-019, F-001.

**Business value:** Companies can expose export generation, reconciliation, and other APIs that return a job reference rather than completing within one short request.

**Current delta:** The reviewed request mapping describes a single operation and bounded timeout, not a source-declared job lifecycle. [R6, R10]

**Deliver:** Bind documented submit/status/result/cancel operations and source job identifiers into a typed descriptor. Return the job reference promptly; the external consumer requests subsequent status/result operations. Do not build an autonomous worker loop, invent cancellation where absent, or convert an unknown submission outcome into success. Use protocol task features only when supported by the pinned SDK and client, with explicit interoperability tests.

**Acceptance:** Completion, failure, expiry, unsupported cancellation, disconnect, duplicate submission, and unauthorized job lookup are correct. Upstream remains the source of durable business-job state. **Rationale:** Business API lifecycle coverage within the existing deterministic model. [R2, R6]

### [ ] F-021 — Consumer impact analysis and deprecation tracking

**Priority / effort:** P2 / M. **Type:** Extend existing build diffs. **Dependencies:** F-002, F-005; correct existing diff/fingerprint defects.

**Business value:** Before changing an API's MCP representation, product teams can identify which consuming applications may break and notify their owners.

**Current delta:** Operation/schema/document diffs exist; they are not a consumer-specific compatibility assessment. [R1, R3, R7]

**Deliver:** Classify tool removals/renames, required-argument changes, auth changes, output-schema changes, and declared deprecations. Join affected operation IDs to actual consumer usage or explicit registered dependencies, keeping inferred and declared dependencies separate. Produce a machine-readable change report and retirement notices. Preserve one active runtime per project; do not serve old/new API versions side by side or hide breakage behind compatibility wrappers.

**Acceptance:** A synthetic breaking change identifies affected consumers with evidence; nonbreaking description changes are distinguished; never-used and unknown dependencies are labeled honestly; historical reports remain immutable. **Relevant precedent:** Automated generated-client/MCP lifecycle management in Stainless. [C3]

### [ ] F-022 — Business-scenario and tool-discoverability evaluation

**Priority / effort:** P2 / M. **Type:** Extend structural/protocol validation with task-oriented evidence. **Dependencies:** F-007, F-008.

**Business value:** Demonstrate that an external assistant can find the correct business capability, not merely that every endpoint became a syntactically valid tool.

**Current delta:** Existing validation checks coverage and representative protocol execution; that does not measure ambiguous descriptions or business-task discoverability. [R3, R7]

**Deliver:** Store representative business questions, expected operation choices, valid arguments, and fixture outcomes per project. Evaluate discovery deterministically and optionally use build-time structured AI for semantic selection assessment. Keep all execution on existing mocks/fixtures; no live customer API mutation or built-in agent service. Report accuracy, ambiguity, excluded-case coverage, context size, and regression by build; label model-dependent results.

**Acceptance:** Known good/ambiguous/wrong tool cases are distinguished; altered semantics cause a detectable regression; structural fidelity remains mandatory; evaluation is separately invokable and not added to deployment. **Relevant precedent:** Curated-tool emphasis in FastMCP and search-oriented generated servers. [C5, C3]

### [ ] F-023 — Non-chat API/MCP contract playground

**Priority / effort:** P2 / M. **Type:** Extend operation and validation workspaces. **Dependencies:** F-007; reuse existing validation harness.

**Business value:** Builders diagnose field mappings, serialization, authentication requirements, and response shapes without writing a separate test client.

**Current delta:** Operation/schema views and validation exist; an interactive request-to-MCP diagnostic workflow is an additional operator capability. [R3, R9]

**Deliver:** Add schema-driven forms, source/manifest side-by-side mapping, mock response selection, serialized-request previews with redacted auth, and downloadable fixture cases. Default to local mock execution. An optional real connectivity check must be explicitly invoked, limited to configured non-mutating diagnostic operations, and use existing authorization. No conversational assistant, new execution backend, or automatic live business testing.

**Acceptance:** Nested/form/multipart inputs serialize exactly; previews never reveal secrets; default execution causes no network business effects; generated cases can run in the existing test harness. **Rationale:** Enterprise developer-experience extension of the current UI and validation boundary. [R3, R9]

### [ ] F-024 — Private capability catalog and registry-compatible metadata

**Priority / effort:** P2 / M. **Type:** Extend project listing and artifact distribution. **Dependencies:** F-004, F-009.

**Business value:** Employees can discover the company's available MCP-enabled products, owners, supported capabilities, and connection instructions in one place.

**Current delta:** Project administration exists; this adds a permission-filtered consumer catalog, not a proxy across projects. [R1, R9]

**Deliver:** Provide searchable product entries with owner, business domain, endpoint, authentication requirements, support contact, active artifact identity, and observed health. Generate schema-validated registry-compatible metadata for the company's chosen private registry. Keep catalog delivery separate from tool execution; consumers connect to the original project endpoint. Private endpoints/specifications must never be published to the public MCP Registry by default.

**Acceptance:** Unauthorized projects remain undiscoverable; metadata points to the exact configured endpoint/build; private exports validate against the selected registry schema; public publishing requires an explicit separate operator action. **Relevant precedent:** Registry ecosystems and ContextForge discovery; official guidance distinguishes public and private registries. [C7, S2]

### [ ] F-025 — Lifecycle notifications and operational integrations

**Priority / effort:** P2 / M. **Type:** Extend existing lifecycle/audit events. **Dependencies:** F-005, F-021 where applicable.

**Business value:** Notify the right team when a build fails, credentials approach expiry, a source changes, or an endpoint becomes unavailable.

**Current delta:** Status and audit information exist; the additional outcome is reliable delivery into the company's existing operational tools. [R1, R7, R9]

**Deliver:** Add project-level subscriptions and a signed generic webhook integration, with optional message templates for company-managed Slack/Teams/incident endpoints. Reuse existing durable job infrastructure and dedicated HTTP clients; provide event IDs, retry/backoff, deduplication, delivery history, and secret-free payloads. Configure supported events explicitly. Notifications do not autonomously perform business actions or become a new event broker.

**Acceptance:** Repeated events are identifiable, failed delivery retries safely, private URLs pass destination controls, and expired credentials/failed builds reach only their configured recipients. **Rationale:** Operational usefulness derived from MCPlica's existing events and enterprise observability patterns. [R7, C7]

### [ ] F-026 — Automated backup, restore, and project migration utilities

**Priority / effort:** P2 / M. **Type:** Extend documented backup and secret-free export procedures.

**Business value:** Recover a company installation and transfer a product between company-controlled hosts with verifiable state rather than manual database/file copying.

**Current delta:** Operations documentation and build exports exist; automated consistency checks and recovery workflows are the new deliverable. [R1, R3]

**Deliver:** Add operator utilities covering authoritative database state, immutable artifacts, configuration, required encryption-key references, and rebuildable-index metadata. Support whole-installation restoration and an explicitly scoped project transfer with identity remapping rules. Never export plaintext secrets or imply that a manifest alone backs up the platform. Validate content hashes, schema compatibility, source bindings, and runtime prerequisites before activating restored state.

**Acceptance:** Restore a populated fixture installation, rebuild derived indexes, and verify projects/builds/permissions/secret references. A partial or incompatible backup fails clearly. A project transfer cannot retain foreign-host routing or accidentally activate two serving instances. **Rationale:** Company-controlled recovery extending the stated self-hosting model. [R1–R3]

### [ ] F-027 — Searchable, portable documentation resource bundles

**Priority / effort:** P3 / M. **Type:** Extend embedded documentation resources. **Dependencies:** F-001, F-008, F-018 where binary material is included.

**Business value:** Agents can retrieve the relevant product instructions alongside API tools, including when the Builder Plane is offline.

**Current delta:** Documentation resources already exist and contain inline content. The addition is bounded local search and scalable packaged delivery. [R4, R6]

**Deliver:** Package larger documentation sets as immutable, hashed resource content referenced by the existing artifact, rather than inflating every tool listing or manifest. Build a local text index and preserve source version, section, and citation metadata. Runtime search/read stays local and permission-aware; no runtime Milvus/LLM or external documentation-fetch service. Return excerpts and explicit bounds instead of loading every document into context.

**Acceptance:** A large resource fixture remains searchable offline; exact citations resolve; tampered content is rejected; excluded resources cannot be discovered; byte/page limits hold. **Relevant precedent:** Stripe/Stainless documentation search, adapted to MCPlica's offline serving boundary. [C17, C3]

### [ ] F-028 — Reusable business API configuration blueprints

**Priority / effort:** P3 / M. **Type:** New reusable configuration content, not a new connector engine. **Dependencies:** F-007, F-010.

**Business value:** Accelerate repeatable deployments for customer support, CRM, inventory, procurement, HR self-service, and reporting use cases.

**Current delta:** A project can already ingest a specification; blueprints add reusable business semantics, safe operation profiles, and fixture examples. [R3, R6]

**Deliver:** Create versioned, source-backed configuration packs with required API operation/schema signatures, suggested tool descriptions, capability groups, examples, and acceptance fixtures. Install into existing project configuration with a visible diff. Require matching authoritative API inputs; do not claim support for a named vendor from generic documentation alone or ship credentials. Pack changes must not silently alter existing builds.

**Acceptance:** A matching API installs cleanly; a mismatched API receives precise unsupported mappings; updates preserve deliberate project overrides; no tool is invented without source operations. **Relevant precedent:** Pipedream's curated integration experience, narrowed to configuration reuse. [C14]

### [ ] F-029 — Explicitly compiled, single-project business task tools

**Priority / effort:** P3 / L. **Type:** Extend deterministic execution mappings. **Dependencies:** F-007, F-019, F-022.

**Business value:** Expose a well-defined operation such as “create a customer and its support case” without requiring every external agent to reconstruct a fragile sequence.

**Current delta:** The architecture permits explicitly modeled deterministic mappings, but the reviewed RequestMapping describes one HTTP operation. [R2, R6]

**Deliver:** Compile operator-authored, bounded sequential steps referencing existing operations within one project. Validate data bindings and source schemas; invoke each step through the same canonical executor. Preserve raw operation coverage and separately identify task-tool coverage. Declare partial-success behavior and any source-supported compensation; do not promise cross-API atomicity. No loops, arbitrary code, AI-selected steps, cross-project aggregation, autonomous triggers, or separate workflow engine.

**Acceptance:** A fixture sequence produces the expected calls and typed result; missing dependencies fail compilation; a midway failure reports exact completed steps; retries honor source idempotency and cannot duplicate completed effects blindly. **Rationale:** A targeted business abstraction, not adoption of Stainless code mode or a general agent platform. [R2, C3]

### [ ] F-030 — Signed project-artifact distribution and verification

**Priority / effort:** P3 / M. **Type:** Extend project export; distinct from existing runtime-image/release signing. **Dependencies:** F-010, F-024.

**Business value:** Companies can distribute a generated MCP capability internally and verify exactly which API source, configuration, and compiler produced it.

**Current delta:** Export hashes and release automation exist; per-project attestations and trusted import/distribution are an additional artifact-level outcome. [R1, R3, R6]

**Deliver:** Attach a verifiable provenance statement to a project export: source/configuration hashes, compiler/runtime compatibility, validation evidence, and configured trusted signer identity. Sign using company-controlled keys through a dedicated client. Support configured internal artifact repositories and verify signatures/digests at import. Signing is an automated integrity check, not a human approval workflow. Secrets remain external references.

**Acceptance:** Valid signatures and all referenced hashes verify; tampered manifests/resources or unknown signers fail; restoring an old compatible signed build does not rewrite its evidence. **Rationale:** Extension of MCPlica's existing immutable artifact model, not a claim that competitors lack signing. [R1–R3]

### [ ] F-031 — Build-data privacy controls and processing visibility

**Priority / effort:** P2 / M. **Type:** Extend existing documentation-in-analysis and privacy controls.

**Business value:** A company can see and minimize which API descriptions, examples, and documents leave its environment during AI-assisted builds.

**Current delta:** The product documents OpenRouter as an external processor and an option to include documentation in analysis. More granular data selection and processing evidence are an additional capability. [R3]

**Deliver:** Add source/section inclusion policy, explicit exclusions for sensitive fields/examples, deterministic redaction, and a preview of the effective external context. Record model/provider-policy configuration, source references, redaction policy version, and permitted accounting metadata without storing hidden reasoning. Validate supported provider-routing controls through the existing OpenRouter client. Avoid unsupported promises of regional confinement, zero retention, or legal compliance. Privacy settings are configuration, not per-build approval steps.

**Acceptance:** Sentinel secrets and excluded sections never reach mocked provider requests; changing privacy policy changes build-context identity; the UI accurately explains what was sent; all normal source-to-runtime mappings remain unchanged. **Rationale:** Direct extension of MCPlica's stated data-privacy requirement. [R3]

### [ ] F-032 — Multilingual business terminology and tool documentation

**Priority / effort:** P3 / M. **Type:** Extend semantic metadata and discovery. **Dependencies:** F-007, F-008.

**Business value:** International teams can ask for the same capability using Arabic, English, or company-specific terminology without publishing duplicate executable tools.

**Current delta:** Human-readable names/descriptions and documentation exist; a versioned locale/glossary layer is a further semantic capability. [R3, R6]

**Deliver:** Add locale-aware descriptions, examples, and business synonyms while retaining one stable canonical operation/tool identity and unchanged parameter semantics. Validate any translations at build time; preserve the original source and terminology owner. Compile searchable multilingual text into the local discovery index. Support right-to-left rendering where displayed in the existing UI; do not introduce runtime translation models.

**Acceptance:** Equivalent Arabic/English queries resolve to the same permitted operation, ambiguous terms remain distinguishable, numeric/date/unit meanings survive examples, and all runtime requests are identical regardless of description locale. **Rationale:** Company terminology extension, with multilingual documentation search illustrated by Stripe. [C17]

## 6. Delivery order and measurable business outcomes

### First outcome: connect a real business consumer safely

Use **F-002 → F-001 → F-007 → F-008 → F-009**, with **F-005/F-006** for attributable operations. For an installation shared by teams, include **F-003/F-004** before broad internal onboarding. Resolve the existing security/lifecycle defects before depending on new access controls.

Measure setup steps/time, unauthorized-call rejection, correct-tool discovery on a fixed task set, context bytes returned, and explainable operational outcomes. No savings percentage is assumed.

### Second outcome: reduce repeated integration maintenance

Use **F-010 → F-011 → F-021**, then **F-022/F-023/F-025**. Measure duplicate builds avoided, time to identify an API change's consumers, stale-source detection, and reproducibility of reported failures. No automatic live API mutation or background model spending is enabled by default.

### Third outcome: deepen an identified enterprise workflow

Select **F-013/F-014/F-015/F-016** for identity/data requirements, or **F-017/F-018/F-019/F-020** for reporting and transactional API requirements. Add the P3 capabilities only when a customer needs that outcome. A finance reporting customer and an internal support customer need not receive the same implementation order.

## 7. Business scenario map

| Company scenario | Useful feature combination | Outcome to validate |
| --- | --- | --- |
| Internal support assistant | F-001, F-007, F-008, F-016, F-019 | Correct ticket/order operations, restricted sensitive fields, safe handling of uncertain writes. |
| HR self-service assistant | F-003, F-004, F-013, F-016 | Corporate login plus actual upstream user permissions; no cross-employee data exposure. |
| Inventory/procurement reporting | F-008, F-017, F-018, F-020 | Complete bounded retrieval and source-backed report jobs/downloads. |
| Platform/API engineering team | F-010, F-011, F-021, F-022 | Repeatable configuration and visible consumer impact of source changes. |
| Security/operations team | F-005, F-006, F-012, F-014, F-025 | Attributable activity, bounded traffic, managed secrets, and actionable notifications. |
| Self-hosted enterprise recovery | F-024, F-026, F-030 | Discoverable, verifiable project artifacts and tested restoration. |

These are proposed use cases, not claims that MCPlica currently performs these workflows or has integrations with a particular business system.

## 8. Deliberately excluded directions

Do not turn this backlog into a hosted SaaS billing platform, broad integration marketplace, built-in chat/agent product, code-execution service, or cross-project MCP federation gateway. Do not add runtime prompt-injection “guarantees” based on a classifier; preserve deterministic boundaries and upstream permissions instead.

GraphQL/gRPC/SOAP/native Swagger 2 ingestion, arbitrary proprietary documentation connectors, mandatory Kubernetes, and OCR/transcription are excluded from this implementation backlog because the authoritative product scope currently excludes them. A future source adapter would require a separately defined product change and must still feed the same canonical compiler, not a parallel runtime. [R3]

Ordinary fixes for source restoration, index isolation, revocation, build ownership, export startup, configuration errors, and other entries in `issues_002.md` remain necessary engineering work, not new competitive feature claims.

## 9. Evidence index

### MCPlica repository evidence

All repository links below are pinned to the reviewed commit. They identify current behavior and the existing component boundaries to extend; they do not prove that every unrelated repository file was examined.

- **R1 — Product overview and implemented surface:** [README.md](https://github.com/yazeedhasan97/MCPlica/blob/2273e46d79104ba661f1a6efbff0951d3a9597b0/README.md).
- **R2 — Architecture and non-negotiable constraints:** [docs/architecture.md](https://github.com/yazeedhasan97/MCPlica/blob/2273e46d79104ba661f1a6efbff0951d3a9597b0/docs/architecture.md), especially sections 3–7.
- **R3 — Product requirements and exclusions:** [docs/product_requirements.md](https://github.com/yazeedhasan97/MCPlica/blob/2273e46d79104ba661f1a6efbff0951d3a9597b0/docs/product_requirements.md), especially source/build/authentication requirements, NFR-014, and section 12.
- **R4 — Runtime tool/resource listing and invocation:** [mcp_runtime/app/server/factory.py](https://github.com/yazeedhasan97/MCPlica/blob/2273e46d79104ba661f1a6efbff0951d3a9597b0/mcp_runtime/app/server/factory.py), `build_server()`, `_page()`, and `build_app()`.
- **R5 — Runtime static/OIDC identity handling:** [mcp_runtime/app/auth/inbound.py](https://github.com/yazeedhasan97/MCPlica/blob/2273e46d79104ba661f1a6efbff0951d3a9597b0/mcp_runtime/app/auth/inbound.py), `StaticBearerTokenVerifier`, `OidcTokenVerifier`, and `build_inbound_auth()`.
- **R6 — Shared tool, resource, request, and authentication contracts:** [packages/contracts/src/mcp_contracts/manifest.py](https://github.com/yazeedhasan97/MCPlica/blob/2273e46d79104ba661f1a6efbff0951d3a9597b0/packages/contracts/src/mcp_contracts/manifest.py), `MCPTool`, `MCPResource`, `RequestMapping`, `AuthProfile`, and `MCPManifest`.
- **R7 — Existing source/build/access/lifecycle findings and component locations:** [issues_002.md](https://github.com/yazeedhasan97/MCPlica/blob/2273e46d79104ba661f1a6efbff0951d3a9597b0/issues_002.md). Treat this as the prior static findings register, not new test evidence.
- **R8 — Control-plane identity model:** [backend/app/domain/auth.py](https://github.com/yazeedhasan97/MCPlica/blob/2273e46d79104ba661f1a6efbff0951d3a9597b0/backend/app/domain/auth.py), `UserRole`, `UserAccount`, and `AuthPrincipal`.
- **R9 — Existing administrative workspaces:** [frontend/src/app.tsx](https://github.com/yazeedhasan97/MCPlica/blob/2273e46d79104ba661f1a6efbff0951d3a9597b0/frontend/src/app.tsx), project, operation, build, validation, deployment, and user routes.
- **R10 — Runtime HTTP execution, limits, and response formats:** [mcp_runtime/app/clients/api_client.py](https://github.com/yazeedhasan97/MCPlica/blob/2273e46d79104ba661f1a6efbff0951d3a9597b0/mcp_runtime/app/clients/api_client.py), `ApiClient.execute()` and `UpstreamResult`.

### Competitor and practitioner primary sources

Accessed 2026-09-01. These are documentation snapshots, not contractual feature/availability commitments. Published capabilities can differ by product, hosting mode, or release. No pricing, market-share, or independently measured performance comparison is asserted.

- **C1:** Speakeasy — [Standalone MCP generation](https://www.speakeasy.com/docs/standalone-mcp/overview).
- **C2:** Speakeasy — [Tool customization, scopes, and annotations](https://www.speakeasy.com/docs/standalone-mcp/customize-tools).
- **C3:** Stainless — [MCP generation and code-tool model](https://www.stainless.com/docs/mcp/); [January 13, 2026 code-mode-only change](https://www.stainless.com/changelog/mcp-servers-now-support-code-mode-only/); [product workflow description](https://www.stainless.com/products/mcp/).
- **C4:** Stainless — [Pre-registered OAuth application support](https://www.stainless.com/docs/mcp/oauth/).
- **C5:** FastMCP — [OpenAPI integration and customization](https://gofastmcp.com/integrations/openapi); [tool transformations](https://gofastmcp.com/servers/transforms/tool-transformation).
- **C6:** FastMCP — [Tool search and authorization-aware visibility](https://gofastmcp.com/servers/transforms/tool-search).
- **C7:** IBM ContextForge — [Overview](https://ibm.github.io/mcp-context-forge/latest/overview/); [feature documentation](https://ibm.github.io/mcp-context-forge/latest/overview/features/); [project documentation](https://ibm.github.io/mcp-context-forge/).
- **C8:** AWS — [AgentCore OpenAPI targets and outbound authorization](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-schema-openapi.html).
- **C9:** AWS — [Gateway search/policy configuration](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-create.html); [fine-grained access-control patterns](https://aws.amazon.com/blogs/machine-learning/apply-fine-grained-access-control-with-bedrock-agentcore-gateway-interceptors/).
- **C10:** Microsoft — [MCP servers in Azure API Management](https://learn.microsoft.com/en-us/azure/api-management/mcp-server-overview).
- **C11:** Composio — [Session identity, scope, discovery, and authentication](https://docs.composio.dev/docs/how-composio-works); [sessions through MCP](https://docs.composio.dev/docs/sessions-via-mcp).
- **C12:** Arcade — [Curated MCP gateways](https://docs.arcade.dev/en/operate/governance/mcp-gateways).
- **C13:** Arcade — [Enterprise operator setup and identity/audit outcomes](https://docs.arcade.dev/en/operate/quickstart). Search-indexed official documentation was available; a direct page fetch failed during this review.
- **C14:** Pipedream — [MCP tools, credential isolation, and connection model](https://pipedream.com/docs/connect/mcp).
- **C15:** GitHub — [Official MCP server configuration](https://github.com/github/github-mcp-server/blob/main/docs/server-configuration.md); [toolset configuration guidance](https://docs.github.com/en/copilot/how-tos/provide-context/use-mcp-in-your-ide/configure-toolsets).
- **C16:** Atlassian — [Rovo MCP authentication and authorization](https://developer.atlassian.com/cloud/rovo-mcp/guides/authentication-and-authorization/), updated June 30, 2026.
- **C17:** Stripe — [MCP tools, onboarding, and session management](https://docs.stripe.com/mcp).

### Standards references

- **S1:** Model Context Protocol — [Published 2025-11-25 authorization specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization). This is the explicitly referenced published revision, not a claim that an unverified draft is supported by MCPlica.
- **S2:** Model Context Protocol — [Registry purpose and private-server guidance](https://modelcontextprotocol.io/registry/about).
