# MCPlica — Detailed Implementation and Business Delivery Plan

**Repository:** `yazeedhasan97/MCPlica`  
**Target branch:** `master`  
**Planning baseline:** `aac31ef30edf178587cab7234f173cec322a14a9`  
**Date:** 2026-09-01  
**Status:** The 55 `issues_002.md` correction items were completed and verified on 2026-09-02. Feature proposals remain governed by their own roadmap status.
**Coverage:** All 55 findings in `issues_002.md` and all 32 proposals in `todo_features.md`, plus the first-business-workflow, operating-evidence, and adoption work discussed subsequently.

### Navigation

[Scope and rules](#1-purpose-source-ownership-and-limits) · [First outcome](#2-first-business-outcome-and-open-inputs) · [Phases](#3-execution-sequence-and-milestones) · [Baseline](#4-ip-0-establish-the-execution-baseline) · [All 55 corrections](#5-foundation-correction-packages-all-55-findings) · [Migrations](#6-cross-cutting-data-contract-and-migration-design) · [First integration](#7-ip-3-deliver-the-first-complete-business-integration) · [All 32 features](#8-feature-implementation-specifications-all-32-proposals) · [Dependencies](#9-implementation-ordering-and-integration-dependencies) · [End-to-end scenarios](#10-required-end-to-end-and-adversarial-scenarios) · [Testing](#11-test-strategy-commands-and-per-item-definition-of-done) · [Business evidence](#12-ip-9-operating-evidence-adoption-and-commercial-readiness) · [Traceability](#13-execution-tracking-and-evidence-protocol) · [Handover](#14-completion-and-handover) · [References](#15-references-and-verified-planning-inputs)

### 2026-09-02 execution record

All 55 correction items were rechecked against checkout `708401dc47a7684c8c95ab0e4061d595657c57dc`. Twelve were already correctly implemented and were retained with explicit regression coverage; the other 43 were applicable and were fixed in the existing architecture. The schema advances linearly from `0020` through `0025`. Per-finding evidence and final validation are in [`docs/evidence/issues-002-closure.md`](docs/evidence/issues-002-closure.md). This closes the issue register in repository scope; it does not change the status of feature proposals or claim promotion to an external production host.

## 1. Purpose, source ownership, and limits

Deliver one demonstrably useful company API integration before expanding into the complete feature backlog. Correct the existing canonical system, prove the first integration end to end, then add capabilities in dependency order. This document contains implementation work, not another competitor survey.

The source findings are a static-review register, not 55 reproduced failures; the previous exhaustive every-file audit was not completed. Reproduce or otherwise verify each applicable finding against the implementation commit before changing code. An issue already fixed upstream must not be implemented again. Absence of a local reproduction is not proof of correctness. The feature proposals are not validated customer demand. [R1], [R2]

### 1.1 Document ownership

| Document | Responsibility |
| --- | --- |
| `issues_002.md` | Finding description, evidence, severity, remedy, and issue disposition. Preserve IDs. |
| `todo_features.md` | Feature purpose, business value, original priority, and product boundaries. Preserve IDs. |
| **Root `implementation_plan.md`** | Detailed post-baseline execution work packages, dependencies, migrations, acceptance scenarios, and evidence linkage. |
| `docs/implementation_plan.md` | Existing authoritative overall roadmap and historical implementation sequence. Do not restart its already delivered foundation phases. |
| `docs/product_requirements.md`, `docs/architecture.md`, `docs/design_document.md`, `docs/tech_stack.md` | Authoritative product scope, architecture, detailed contracts, and technology standards. |
| `docs/release/release-checklist.md` | Existing release/operational evidence checklist; update facts, not assumptions. |

During implementation, add a short link in the existing roadmap and documentation index identifying this root file as its post-baseline execution extension. Do not copy this entire plan into `docs/` or maintain two independently editable versions of these tasks. Update the relevant owner specification with each implemented feature. Where a proposed feature requires a bounded product-contract extension, describe that extension explicitly; this plan does not silently override the owner document. [R3], [R4], [R5], [R6]

Historical references to approvals or phase gates must not be implemented as new product behavior. The completion conditions here are verifiable engineering outcomes, not additional human approvals, deployment authority layers, or waiting states. Existing repository/legal policy is not silently removed; external configuration dependencies are recorded honestly, without expanding them into new processes.

### 1.2 Non-negotiable implementation rules

1. Use the existing modular monolith, repositories, dedicated coding clients/providers, shared contracts, React frontend, generic runtime, and Docker/Traefik deployment model. No new architecture, V2 endpoints, duplicate persistence/services, parallel serving implementation, shadow/canary/staging-specific paths, or compatibility wrappers that preserve obsolete execution code.
2. Maintain one active serving runtime/subdomain per project. Do not introduce cross-project execution federation, built-in chat, an agent loop, arbitrary executable scripts, SaaS tenancy, subscriptions, paid entitlements, or billing.
3. PostgreSQL remains authoritative; Redis remains temporary queue/cache state; Milvus remains rebuildable build-side state. No runtime LLM/Milvus dependency or mandatory Builder Plane round trip for each tool call.
4. Preserve source-faithful deterministic mappings, immutable historical builds, ownership boundaries, credential confidentiality, TLS verification, URL/DNS policy, and fail-closed authentication. Ordinary automatic permission checks are required; they are not human approval workflows.
5. Prefer the issue register's remedy. Depart only when reproduction or intervening implementation proves it unsuitable; record the original remedy, conflicting evidence, replacement design, affected contracts, and regression assertions. Do not improvise unsupported API semantics.
6. Keep changes production-safe and bounded. Never use live company mutations as automatic build checks. Mock/fixture implementations belong only in test infrastructure, never as a successful production fallback.
7. Use focused TDD/BDD at affected boundaries. Reuse test harnesses; do not repeatedly run unrelated visual/theme tests. Run the existing broader verification suites at integration milestones and retain their normal CI policy. **Do not add tests to the deployment process.**
8. Keep a logical change complete across database, domain, API, contracts, runtime, UI, tests, and documentation. Use one canonical implementation even when schema migrations need multiple ordered steps. Prefer a documented short maintenance window over an invented zero-downtime parallel path.

## 2. First business outcome and open inputs

### 2.1 Working hypothesis, not an invented customer commitment

The initial customer profile to validate is an internal platform/API engineering team exposing one existing company API to its chosen external MCP client. The initial fixture workflow is: find a customer/order or support record, retrieve status with explicit pagination, and create one support case in a designated test account when the source supports it.

Use the customer's actual source specification and business task once supplied. Until then, implement and verify against representative fixtures; do not invent a customer, API entitlement, production endpoint, identity-provider registration, budget, or signed agreement.

The first delivered package is **F-002, F-001, F-007, F-005, F-006, F-009, and F-022**. F-022 is deliberately used earlier than its original P2 position to test whether tools are useful, not merely present. Add F-008 for a catalog that needs selective discovery, F-017 for a task needing complete collection retrieval, and F-013 before any task requires upstream end-user permissions. Never substitute a broadly privileged service credential for missing delegation. [R2]

### 2.2 Capture these inputs in the existing project/context documentation

| Input | Required record | Work that can proceed without it |
| --- | --- | --- |
| First business workflow | Actor, task, input, expected output, permitted side effects, failure/recovery expectations | Source-faithful fixture workflow and correctness fixes |
| API/client | Exact specification hash/revision, MCP client/version, authentication mode, supported operations | Local integration fixtures and official-client protocol tests |
| Identity/security | IdP metadata, application audience, consumer grants, permissible data processing | Client interfaces, negative tests, secret-safe defaults |
| Operating envelope | Host resources, expected concurrency, latency objective, retention and recovery requirements | Reproducible measurements; no unsupported sizing promise |
| Commercial offer | One-API integration scope, deliverables, support coverage, exclusions, success measures | Technical evidence and installation documentation |

These are explicit external inputs, not approval steps. Mark an integration needing unavailable credentials as `Awaiting external input` while completing its repository-controlled work. Do not mark it live-verified from mocks.

## 3. Execution sequence and milestones

Phase identifiers below use `IP-` to avoid confusion with the historical phases in `docs/implementation_plan.md`. Original feature P1/P2/P3 priorities remain unchanged except for documented sequencing needed by the first workflow.

| Phase | Outcome | Included work | Dependencies |
| --- | --- | --- | --- |
| IP-0 | Reproducible baseline and bounded first-workflow specification | Inventory, source verification, test baseline, evidence setup, business inputs | None |
| IP-1 | Correct source/build/lifecycle/security state | R-WORKERS, R-SOURCE, R-ACCESS | IP-0; coordinate shared migrations |
| IP-2 | Operable installation and consistent contracts | R-DEPLOY, R-CONTRACT, R-OPS; final disposition of every finding | IP-1 where state/identity is shared |
| IP-3 | First usable, attributable company integration | F-002 → F-001; F-007; F-005 → F-006; F-009; F-022 | Correct affected foundation behavior |
| IP-4 | Company identity, large catalogs, and resource/privacy controls | F-003, F-004, F-008, F-012, F-031 | IP-3 contracts; move required items into first workflow rather than bypassing them |
| IP-5 | Repeatable source maintenance and developer operations | F-010 → F-011; F-021; F-023; F-025 | F-004, source identity, invocation evidence |
| IP-6 | Enterprise credential and data boundaries | F-014, F-015, F-013, F-016 | Consumer policy and secure lifecycle |
| IP-7 | Deeper reporting and transactional API coverage | F-017, F-018, F-019 → F-020 | Access policy; relevant upstream contracts |
| IP-8 | Portable distribution and targeted business abstractions | F-024, F-026, F-027, F-028, F-029, F-030, F-032 | Per-feature dependencies in section 8 |
| IP-9 | Measured operating/adoption evidence and reconciled documentation | Whole-journey checks, performance/recovery measurements, design-partner feedback, support package | Run first for IP-3, then refresh for later delivered scope |

**Milestone A:** All 55 findings have an evidence-backed disposition; no reproduced unresolved High issue affects the delivered system. **Milestone B:** The first business journey completes with an actual external MCP client and recorded limits. Manual use of the existing documented backup/restore procedure is required for an operating handover even before F-026 automates it. **Milestone C:** The remaining implemented features meet their own acceptance conditions and the shared regression suite. **Milestone D:** Installation, maintenance, and business value have observed evidence from company-controlled use.

Do not wait for IP-8 to validate adoption. Later proposals remain planned until their scope is executed and proven; the plan does not require building speculative large capabilities before delivering Milestone B.

## 4. IP-0 — Establish the execution baseline

1. Fetch current `master`; record the execution commit, dirty-worktree state, dependency locks, schema head(s), runtime version, and frontend generation state. Compare against the planning baseline and reconcile any newly changed issue/feature status before implementation.
2. Enumerate tracked files using the repository tree or `git ls-files`; record review coverage for touched components and their callers/tests. Do not equate a file inventory, lint pass, or automated scan with a line-by-line review.
3. Read the owner specifications, source registers, Makefile, CI commands, package manifests, and existing fixtures. Verify the tools already available to the coding agent and use relevant installed skills without introducing duplicate toolchains.
4. Establish a disposable database/Redis/Milvus and local Docker test environment using the same production code and configuration contracts. Use test data and isolated volumes; do not add a special serving implementation.
5. Run the current supported baseline commands from locked dependencies, recording failures and missing prerequisites separately. Do not blindly regenerate lockfiles to make installation succeed.
6. Build a compact fixture set: two projects; two consumers; two source revisions plus A→B→A restoration; an excluded operation; nested input/output schemas; token rotation/revocation; a successful/failed deployment; long-running/cancelled worker cases; large documentation. Reuse existing fixtures first.
7. Record the first-workflow inputs in section 2 and the acceptance case list in section 10. Keep actual live credentials outside repository files and reports.
8. Link one proposed `docs/evidence/implementation-progress.md` from the existing evidence index, if no equivalent execution record exists. This is an evidence log, not a second roadmap. Correct the documentation ignore issue before adding new tracked evidence.

**Completion:** Repeatable baseline commands, exact failures/limitations, source-register versions, fixture identities, and an honest item-status inventory are recorded. No speculative defect is marked fixed.

## 5. Foundation correction packages — all 55 findings

Each task below inherits the full Description, Location & Evidence, Criticality, Recommended Solution, and Testing & Validation of its matching item in [issues_002.md](issues_002.md). The table adds execution order and implementation details. Source severities are inherited, not re-estimated here. IDs are the **repository** IDs; do not reuse a stale downloaded copy that renumbers later findings.

For each item: write the smallest reproduction or invariant test; record whether the current implementation violates it; fix the canonical boundary if confirmed; run its related negative and integration cases; record exact evidence. If a claim is disproved, retain its ID and record `Not applicable—evidence`, with the test and technical explanation. Never delete a finding to improve counts.

### R-WORKERS — Execution ownership, cancellation, locking, and cleanup

**Phase:** IP-1. **Items:** `ISS-002-007`, `ISS-002-008`, `ISS-002-009`, `ISS-002-015`, `ISS-002-034`, `ISS-002-035`, `ISS-002-036`, `ISS-002-037`, `ISS-002-038`, `ISS-002-046`.

Implement ownership and lock ordering before relying on lifecycle retries. Use real PostgreSQL concurrency tests, not only mocks. Reuse command/admission/cleanup models; do not introduce a second scheduler.

#### ISS-002-007 — Cancellation acknowledgement recovery

**Implementation area:** `backend/app/jobs/build.py`, admission repository, build service/pipeline, cleanup.

**Work:** Distinguish requested cancellation from superseded ownership. Route cooperative cancellation and heartbeat-driven interruption through one idempotent acknowledgement/cleanup transaction. Extend the existing dispatcher to finalize cancellation for expired/dead owners without rerunning stages. Do not clear durable references before cleanup targets are captured.

**Proof of resolution:** Cancel a long stage immediately before heartbeat; kill the worker after request; assert eventual CANCELLED with acknowledgement, released admission, accurate cleanup, and ability to start another build.

#### ISS-002-008 — Build fencing

**Implementation area:** `backend/app/jobs/build.py`, admission/build/AI-run/index repositories and pipeline.

**Work:** Carry the existing admission token through every ownership-sensitive stage/result publication. Conditional writes must match current token and permitted state. Stop starting provider work after the last confirmed lease expires; record/discard late results rather than publishing them. Apply cancellation recovery consistently and use database time for lease decisions.

**Proof of resolution:** Let worker A stall through expiry, let B reclaim, then resume A. A cannot complete/fail B’s build, publish artifacts or accepted AI results, or corrupt generation state.

#### ISS-002-009 — Runtime command fencing

**Implementation area:** `backend/app/repositories/runtime_commands.py`, command executor/dispatcher, queue client, runtime manager.

**Work:** Give execution claims an owner token/epoch, renew during long work, and condition state updates on that owner. Serialize conflicting project lifecycle effects and target exact deployment/container identities. Verify ownership before effects and reconcile observed Docker state after crashes; a lease precheck alone does not guarantee exactly-once external effects.

**Proof of resolution:** Duplicate/reorder queue delivery; pause before and after Docker effects; expire/reclaim the lease. Reject stale finalization, prevent a stale stop from targeting the replacement, and reconcile late external completion.

#### ISS-002-015 — Consistent lifecycle lock order

**Implementation area:** `backend/app/services/deployment/service.py`, project service, deployment/runtime command repositories.

**Work:** Acquire project coordination before deployment rows, with deterministic ordering for multiple deployments, then subject/command locks as required. Read immutable project IDs without taking an inverted mutation lock and revalidate once serialized. Review credential and stop paths against the same order.

**Proof of resolution:** Real PostgreSQL barriers overlap activation, stop, disable, recovery, and credential changes. No lock cycle; active pointers and one-running constraints remain correct.

#### ISS-002-034 — Serialized cleanup totals

**Implementation area:** `backend/app/repositories/cleanup.py`, cleanup models/service.

**Work:** Serialize parent progress aggregation with a consistent job/target lock order, or atomic idempotent transitions followed by authoritative aggregation. Reconcile stale totals and terminal events from actual target states.

**Proof of resolution:** Concurrent completion/failure/skip of different targets yields exact final counters/status after both commits, without relying on a future unrelated refresh.

#### ISS-002-035 — Executable cleanup lease batches

**Implementation area:** `backend/app/services/cleanup.py`, cleanup claim/terminal repositories.

**Work:** Claim only bounded immediately runnable work, renew owned targets, and fence terminal updates to the claim. Preserve reference locking during object deletion and recheck vector references correctly. A leased list is not permanent ownership.

**Proof of resolution:** Slow first deletion plus short leases and two workers cannot let stale owners finalize reclaimed work or remove referenced content; attempts/counts reflect actual work.

#### ISS-002-036 — Retention failure isolation

**Implementation area:** `backend/app/services/cleanup.py` dispatch/retention loops.

**Work:** Handle each project’s retention failure independently, schedule bounded retry, and process already due cleanup even when retention preparation fails. Preserve diagnostic details and avoid immediately retrying a permanently failing project every cycle.

**Proof of resolution:** One failing retention project does not block another project’s object deletion/orphan guard; retry timing is bounded and recovery clears status correctly.

#### ISS-002-037 — Structured resource lifetime

**Implementation area:** `backend/app/main.py`, `jobs/build.py`, dispatcher/client shutdown.

**Work:** Register cleanup as resources are acquired; signal all tasks before bounded waits; cancel/join overdue work; attempt all closes even after failure. Retain original failure context safely.

**Proof of resolution:** Inject failure after every acquisition and stall a dispatcher/close; all earlier resources close and shutdown completes within its configured deadline.

#### ISS-002-038 — Redis socket deadlines

**Implementation area:** `backend/app/clients/cache.py`, `build_queue.py`, `queue.py`, health/configuration.

**Work:** Set validated connect/read deadlines and bounded retry behavior on existing Redis clients, including sync calls executed in threads. Align upper deadlines with actual socket bounds; cancellation alone must not be relied on to stop a blocked thread.

**Proof of resolution:** Unreachable and accept-but-never-reply servers cause bounded health/enqueue/cache failures without accumulating stuck threads; normal recovery and fail-closed rate limiting are retained.

#### ISS-002-046 — Immutable activation evidence

**Implementation area:** `backend/app/repositories/deployments.py`, `domain/deployments.py`, health observations.

**Work:** Do not replace the successful activation proof with a later health observation. Keep original activation binding immutable and represent later health evidence with its actual meaning. Repair only from retained trustworthy evidence.

**Proof of resolution:** Activation then later observation then stop preserves legitimate rollback eligibility; never-activated/tampered records remain ineligible.

### R-SOURCE — Source selection, immutable inputs, and isolated retrieval

**Phase:** IP-1. **Items:** `ISS-002-001`, `ISS-002-002`, `ISS-002-003`, `ISS-002-013`, `ISS-002-031`, `ISS-002-033`.

Coordinate current-selection and frozen-binding migrations before enabling Git synchronization. Keep historical immutable artifacts intact; rebuild derived data deliberately.

#### ISS-002-001 — Scoped vector identities

**Implementation area:** `backend/app/parsers/documentation/chunker.py`, `clients/vector.py`, `providers/milvus.py`, indexing service and shared chunk metadata.

**Work:** Include project, generation, and source-version binding in deterministic row identity; retain the content hash solely for vector-cache reuse. Reconcile retrieval/provenance and generation deletion. Repair derived indexes through the existing indexing path; publish a new build for changed immutable resource manifests instead of rewriting historical artifacts.

**Proof of resolution:** Index identical content in two projects, two generations, and two source bindings; assert distinct scoped rows, idempotent same-generation upserts, and deletion of only the requested generation.

#### ISS-002-002 — Current source selection

**Implementation area:** `backend/app/models/source.py`, repositories/services for sources, build configuration identity, retention.

**Work:** Add a current-version reference and latest observation metadata to the existing source aggregate. Backfill from the existing known current selection; do not pretend to reconstruct lost historical restoration intent. Update selection and HTTP validators atomically on new content and hash reuse; use it in summaries, build binding, and retention.

**Proof of resolution:** Exercise upload and URL A→B→A, A→A, 304 refresh, concurrent updates, and retention; newest accepted content is current while old build bindings and version timestamps stay immutable.

#### ISS-002-003 — Frozen executable source metadata

**Implementation area:** `backend/app/domain/builds.py`, `domain/sources.py`, `models/build.py`, `services/builds/configuration_identity.py`, canonicalization.

**Work:** Freeze source role, dependency aliases, and routing with existing build-source bindings. Compute the canonical executable identity from those frozen inputs and parse from the snapshot, not live ProjectSource fields. Keep historical hash interpretation explicit; records without trustworthy required metadata need a new build rather than fabricated provenance.

**Proof of resolution:** Queue a build, promote another primary and rename an external dependency; assert original parsing inputs remain unchanged, new discovery identity changes, and stale normal deployments are rejected.

#### ISS-002-013 — Bounded canonicalization reads

**Implementation area:** `backend/app/services/canonicalization/service.py`, storage client and configuration.

**Work:** Load only required executable sources/dependencies; form documentation references from immutable metadata. Bound concurrent fetches and total executable bytes before allocation. Keep full documentation parsing in indexing and release buffers promptly.

**Proof of resolution:** Large attached documentation is never read during canonicalization; excessive executable dependencies trigger a clear aggregate limit; valid canonical output remains deterministic.

#### ISS-002-031 — Nonblocking source findings

**Implementation area:** `backend/app/services/sources.py` metadata, domain/API summary models.

**Work:** Compute parse completion from version-specific snapshot/stage evidence independently of finding severity. Preserve warnings/info while populating valid operation/server/auth metadata; never label a truly failed parse valid.

**Proof of resolution:** No-finding, warning-only, info-only, blocking, and pending cases display correct status/counts with exact version/build attribution.

#### ISS-002-033 — Meaningful executable diffs

**Implementation area:** `backend/app/services/builds/diff.py`, canonical projections.

**Work:** Compare resolved server URL/auth mapping and normalized executable schema semantics, excluding incidental source-version provenance. Report genuine provenance/enrichment changes separately. Keep deterministic ordering.

**Proof of resolution:** Stable server key with changed URL is visible; provenance-only version change creates no false executable diff; true method/path/schema/auth changes remain visible.

### R-ACCESS — Credential and authentication lifecycle

**Phase:** IP-1. **Items:** `ISS-002-004`, `ISS-002-005`, `ISS-002-006`, `ISS-002-022`, `ISS-002-029`, `ISS-002-041`, `ISS-002-045`, `ISS-002-049`, `ISS-002-050`.

Depends on corrected transition ordering and execution ownership. Security removal must remain independent from the deployability of a replacement or pending source edit.

#### ISS-002-004 — Transition-aware stop/redeploy

**Implementation area:** `backend/app/services/deployment/service.py`, `repositories/deployments.py`, credential rotation.

**Work:** Detect conflicts using transition ownership, not a blanket STOPPING check. Accept this transition’s predecessor stop while rejecting unrelated active work. Commit the ordered stop/replacement intent together; execute replacement only after predecessor effectiveness. Retain one serving identity and do not simply remove STOPPING from all conflict checks.

**Proof of resolution:** Rotate a used credential with a RUNNING or in-flight deployment; observe committed STOP→DEPLOY ordering. Inject unrelated deployment and failed stop; no self-conflict or premature replacement.

#### ISS-002-005 — Last-token revocation

**Implementation area:** `backend/app/services/mcp_access.py`, deployment service/preflight, runtime secret contract.

**Work:** Count remaining valid verifiers under the project lock. Commit final-token revocation with durable STOP intent rather than an invalid empty-verifier replacement. Never recreate a revoked credential to make deployment valid. Return requested/effective status separately; report stop failure truthfully.

**Proof of resolution:** Revoke the only token, multiple-token subset, expired token, and duplicate request; queue interruption/restart must not roll back the security intent or falsely report revocation effective.

#### ISS-002-006 — Security refresh independent of source drift

**Implementation area:** `backend/app/services/deployment/service.py`, preflight, credentials and MCP access services.

**Work:** Represent a narrow security-refresh intent bound to the exact active build. Validate its artifact, project, compatibility, and current permitted secrets without requiring unrelated pending executable inputs to match. Preserve freshness checks for ordinary deployment; use stop behavior if refreshed security cannot safely serve.

**Proof of resolution:** Deploy A, modify source/routing to B, then rotate/revoke. Only A is refreshed or stopped; B is never implicitly deployed and normal stale-A deployment is still rejected.

#### ISS-002-022 — Shared credential validation

**Implementation area:** `backend/app/domain/credentials.py`, credential schemas/services, shared runtime secrets.

**Work:** Reuse infrastructure-free validators for control-plane accepted material and runtime materialization. Validate Basic username syntax, header names/case-insensitive uniqueness, and header-safe values; do not forbid valid password/client-secret characters unrelated to header serialization.

**Proof of resolution:** Every accepted credential materializes; invalid colon usernames, duplicate-case headers and control characters fail before persistence/lifecycle changes; valid Unicode passwords/query secrets still work.

#### ISS-002-029 — Exact issuer identity

**Implementation area:** `mcp_runtime/app/clients/oidc_client.py`, `auth/inbound.py`, materialization/validation.

**Work:** Preserve the exact configured issuer for discovery and token verification. Construct the discovery URL separately. Check all boundaries, not only the client, for rstrip or URL serialization changing significant paths/slashes. [S1], [S3]

**Proof of resolution:** Slash/no-slash and path issuers accept only their exact configured identity; mismatched discovery issuer and JWT iss fail; configured JWKS does not bypass issuer checks.

#### ISS-002-041 — Bounded asynchronous password work

**Implementation area:** `backend/app/core/auth.py`, user/auth services.

**Work:** Run expensive password operations off the event loop with bounded concurrency. Compute before taking mutation locks where safe, then revalidate under existing uniqueness/last-admin coordination. Preserve hash strength and safe error handling.

**Proof of resolution:** Concurrent hashing does not stall lightweight requests or overwhelm memory; uniqueness, admin count, password verification, cancellation, and secret redaction remain correct.

#### ISS-002-045 — Versioned encryption-key rotation

**Implementation area:** `backend/app/core/crypto.py`, config, composition roots, encrypted credential/settings records.

**Work:** Configure a validated key ring plus active write key using the existing cipher. Reencrypt records in resumable bounded batches with unchanged AAD and version checks. Keep old keys until required records and retained recovery backups can be decrypted or retired under retention policy.

**Proof of resolution:** A→A+B with B active supports old reads/new writes; interruption/retry is idempotent; incorrect AAD fails; removing A too early is detected; no plaintext enters reports.

#### ISS-002-049 — Actual last-active-admin transitions

**Implementation area:** `backend/app/services/users.py`, users repository.

**Work:** Compare current/proposed active-admin membership rather than role alone. Protect only changes that actually remove the final active admin, under existing admin mutation serialization.

**Proof of resolution:** Inactive admin can be demoted; sole active admin cannot; concurrent changes to two active admins leave at least one active.

#### ISS-002-050 — Finite OAuth token lifetime

**Implementation area:** `mcp_runtime/app/clients/oauth_client.py`.

**Work:** Reject boolean, nonfinite, zero/negative, or malformed expires_in values before bounds; document omitted expiry policy and preserve valid numeric handling. Align token/header safety without altering unrelated secret characters.

**Proof of resolution:** True/false, NaN, infinity, strings, omitted, fractional and positive integer cases produce explicit valid finite deadlines or safe authentication failure.

### R-DEPLOY — Installation, configuration, storage, and recovery

**Phase:** IP-2. **Items:** `ISS-002-010`, `ISS-002-011`, `ISS-002-012`, `ISS-002-014`, `ISS-002-016`, `ISS-002-017`, `ISS-002-018`, `ISS-002-043`, `ISS-002-053`, `ISS-002-054`, `ISS-002-055`.

Make the documented install/export paths reproducible, while preserving the distinction between build-side optional dependencies and required serving components.

#### ISS-002-010 — UI/API production host agreement

**Implementation area:** `infra/docker/nginx.conf`, `backend/app/main.py`, production Compose/configuration.

**Work:** Normalize and validate the exact public API/UI authorities. Align the same-origin proxy Host contract with the API allowlist, preserving CSRF, secure cookies, trusted forwarded protocol, and unknown-host rejection. Do not use wildcard Host acceptance to hide mismatch.

**Proof of resolution:** With distinct TLS UI/API domains, verify login, refresh, mutation, reads, event streams, direct API access, and denied unrelated Host headers.

#### ISS-002-011 — Runnable secret-free export

**Implementation area:** `backend/app/services/artifacts.py`, runtime settings/secret loader, export README.

**Work:** Generate all mandatory production settings from the runtime contract, including allowed origin and externally supplied secret-overlay digest. Provide commands/instructions to compute that digest without exporting plaintext secrets. Align image/version, input paths, host, and size limits.

**Proof of resolution:** Generate an export and run the generic runtime with a temporary valid secret bundle; initialization and authenticated listing succeed. Wrong digest/origin fails and no export file contains plaintext credentials.

#### ISS-002-012 — Embedding-capable model catalog

**Implementation area:** `backend/app/clients/ai.py`, provider normalization, settings/build preflight.

**Work:** Verify the provider’s documented modality query against current official documentation and a captured fixture before changing requests. Fetch required text and embedding catalog coverage through one client method, retain capabilities, and distinguish empty/unavailable catalog from unsupported selection. Do not hardcode model IDs.

**Proof of resolution:** Default-text-only versus all-modality fixtures show correct request parameters, embedding selection, settings validation, and build creation; incompatible model selections still fail.

#### ISS-002-014 — Restart behavior

**Implementation area:** `infra/compose.yaml`, `infra/compose.production.yaml`, operations docs.

**Work:** Set explicit restart policy on existing long-running services; retain one-shot migration/init restart=no. Ensure dependency failures recover without recreating authoritative volumes. Document that unhealthy status and automatic process restart are different behaviors.

**Proof of resolution:** Inspect merged configuration; kill representative API/worker processes and restart Docker in a disposable environment. Services recover, state survives, and durable work does not duplicate effects.

#### ISS-002-016 — Upload/spool capacity agreement

**Implementation area:** `backend/app/api/sources.py`, request handling/configuration, Nginx and Compose tmpfs.

**Work:** Define the supported request envelope, file limit, and maximum aggregate concurrent spool usage. Enforce a streamed total-body bound before unsafe multipart allocation, retain storage-level limits, and size/bound spool capacity including envelope overhead. Make disconnect cleanup reliable.

**Proof of resolution:** Boundary and one-byte-over uploads, absent/incorrect Content-Length, multiple concurrent uploads, and disconnects yield bounded disk use and structured errors, not ENOSPC/500.

#### ISS-002-017 — Builder-outage startup isolation

**Implementation area:** `infra/compose.yaml`, `backend/app/api/health.py`, application initialization.

**Work:** Remove builder-only healthy-start coupling from control-plane startup where code supports degraded operation. Keep essential persistence dependencies explicit; optional clients must initialize without preventing management of already deployed projects.

**Proof of resolution:** Start with Milvus unavailable; API/login/existing-project reads operate, dependency status is truthful, builds report unavailable prerequisites, and recovery requires no control-plane rebuild.

#### ISS-002-018 — UID/GID ownership contract

**Implementation area:** `infra/docker/backend.Dockerfile`, runtime-init/deployment-worker Compose, `clients/runtime_files.py`.

**Work:** Choose and enforce one supported worker/runtime ownership configuration. Support custom IDs coherently in image/user setup and narrowly scoped initialization, or reject unsupported combinations early. Keep runtime secrets owner-only and avoid root workers/world-readable fixes.

**Proof of resolution:** Default/custom Linux bind-mount fixtures prove materialization, runtime read, cleanup, restart, and secure modes; unsupported identity combinations fail before deployment.

#### ISS-002-043 — Storage write-readiness capability

**Implementation area:** `backend/app/clients/storage.py`, health/readiness.

**Work:** Use a tiny bounded create/write/flush/remove probe in the existing client without touching user artifacts. Normalize read-only/permission/capacity failures and clean probe files; readiness is not a guarantee of future free space.

**Proof of resolution:** Healthy/read-only/full/denied fixtures report correctly within deadline; no probe leftovers or existing-object mutations; restored permissions recover.

#### ISS-002-053 — Deterministic checksum inventory

**Implementation area:** `MANIFEST.sha256`, existing generation/check scripts and release docs.

**Work:** Define whether the manifest covers source or release inputs. Generate from that exact tracked input set, exclude itself, remove absent entries, and refresh at final artifact state. Do not treat Git blob IDs as SHA-256 content checksums.

**Proof of resolution:** Clean-checkout verification has no absent/duplicate/mismatched entries; add/remove/modify a covered file and observe detection; repeat generation is identical.

#### ISS-002-054 — Consistent runtime image build target

**Implementation area:** `Makefile`, `.env.example`, Compose/runtime version configuration.

**Work:** Resolve the development tag/version from the same documented configuration used by deployment; retain immutable digest-only production rules. Avoid divergent hardcoded tags and never try to build into a digest.

**Proof of resolution:** Default/custom development target exists locally and is selected without surprise pull; production digest configuration is not rewritten.

#### ISS-002-055 — Unique example environment names

**Implementation area:** `.env.example`, existing config checks.

**Work:** Keep one MCP_RUNTIME_VERSION assignment, refer to it in other comments, and detect duplicate names in example configuration. Preserve established variable names and no deployment-time testing.

**Proof of resolution:** Assignment parser finds unique keys; changing the sole version affects all intended consumers; comments/blank optional values do not produce false duplicates.

### R-CONTRACT — Parser, API, provider, and runtime contract consistency

**Phase:** IP-2. **Items:** `ISS-002-019`, `ISS-002-020`, `ISS-002-021`, `ISS-002-023`, `ISS-002-024`, `ISS-002-025`, `ISS-002-026`, `ISS-002-027`, `ISS-002-028`, `ISS-002-030`, `ISS-002-032`, `ISS-002-039`, `ISS-002-040`, `ISS-002-048`.

Consolidate rules at the smallest shared boundary. Update generated contracts and the current frontend client when API shape changes; do not ship competing validation rules.

#### ISS-002-019 — Raw-type exclusion validation

**Implementation area:** `backend/app/schemas/build.py`, operation-exclusion route/service.

**Work:** Type-check raw before-validator input before stripping it; retain normalized length checks. Use the existing request validation envelope, not unexpected AttributeError.

**Proof of resolution:** Null, integer, bool, list, object, whitespace, and length boundaries yield 422 at the right field with no mutation; valid normalized exclusions succeed.

#### ISS-002-020 — Omission versus null in settings

**Implementation area:** `backend/app/schemas/setting.py`, `services/settings.py`, settings API.

**Work:** Define explicit null behavior per field. Required operational values reject null at request validation; nullable retention fields keep their documented reset behavior. Validate the merged object before persistence and normalize expected errors into the existing envelope.

**Proof of resolution:** All fields are tested for omitted/null/valid values; partial updates preserve unrelated values and failed updates leave settings/audit unchanged.

#### ISS-002-021 — Persistent cleared model semantics

**Implementation area:** `backend/app/services/settings.py`, model-settings schemas/UI.

**Work:** Separate absent stored keys from explicitly cleared values. Use one effective-settings resolver for GET, update response, and frozen builds; environment defaults apply only under the documented reset/default rule.

**Proof of resolution:** With environment defaults present, clear and reread each model; GET and build snapshots agree. Omitted keys still inherit defaults and partial edits do not reset other models.

#### ISS-002-023 — Included-operation preflight

**Implementation area:** `backend/app/services/builds/service.py`, readiness/credential mapping, compiler/validator.

**Work:** Freeze exclusions and derive the included operation set once. Apply per-operation routing/auth readiness and compilation to that set, while retaining structural validation necessary to interpret the source safely. Distinguish explicit exclusion from unsupported included operations.

**Proof of resolution:** An excluded operation with unresolved auth/routing cannot block valid included operations; removing its exclusion restores the expected failure; coverage and historical build exclusions stay accurate.

#### ISS-002-024 — One credential selection algorithm

**Implementation area:** `backend/app/services/builds/readiness.py`, `credential_mapping.py`, pure domain contracts.

**Work:** Consolidate compatibility, explicit binding, scope, ambiguity, anonymous alternative, and ordering rules into one pure selector. Feed it adapted discovery/canonical data and consume its typed result in compilation. Eliminate divergent alternative-selection implementations.

**Proof of resolution:** The same edge-case table produces identical readiness/compile decisions, including bad default scopes, changed advertised scopes, explicit candidates, and a usable later alternative.

#### ISS-002-025 — Shared path-template parsing

**Implementation area:** `packages/contracts/src/mcp_contracts/canonical.py`, inventory/validation, compiler/runtime path mapping.

**Work:** Use one balanced-placeholder parser for embedded/multiple placeholders; reconcile inventory and canonical declarations with runtime substitution. Preserve exact parameter names and encoding/traversal rules.

**Proof of resolution:** Files/{id}.json and {lat},{lon} work end to end; malformed braces, missing/extra parameters, encoded separators, and traversal attempts fail consistently.

#### ISS-002-026 — Schema-aware materialization

**Implementation area:** `backend/app/parsers/api_inventory/parser.py`, schema validation tests.

**Work:** Traverse schema-valued keywords rather than every dictionary. Preserve literal default/examples/const/enum objects containing $ref/$defs; retain real definition scope and immutable-source external-reference restrictions.

**Proof of resolution:** Literal annotation payloads remain equal; true nested/cyclic references resolve; original/materialized schema instance acceptance agrees for representative fixtures.

#### ISS-002-027 — Complete local JSON Pointer traversal

**Implementation area:** `backend/app/parsers/api_inventory/parser.py` local resolver.

**Work:** Support object keys, valid array indices, fragment percent-decoding, and ~0/~1 escaping with bounded traversal and deterministic errors. Never fall back to arbitrary network resolution.

**Proof of resolution:** Pointers into allOf/anyOf/prefixItems and escaped keys resolve; malformed, negative, out-of-range, or nonschema targets fail with source attribution.

#### ISS-002-028 — Status-before-media response dispatch

**Implementation area:** `mcp_runtime/app/executor/response_contract.py`, compiler response fixtures.

**Work:** Select the most specific declared status first, then media within that status. Reject a media mismatch instead of falling through to class/default. Preserve explicit absence-of-body versus JSON-null semantics.

**Proof of resolution:** 200/json plus default/text must reject 200/text; class/default apply only when appropriate; test media wildcards, 204, JSON null, and incorrect successful schemas.

#### ISS-002-030 — Document-order DOCX parsing

**Implementation area:** `backend/app/parsers/documentation/docx.py`, chunking/resource fixtures.

**Work:** Traverse supported document body blocks in original order while maintaining heading context for paragraphs and tables. Preserve existing limits and explicit handling of supported nested blocks.

**Proof of resolution:** Heading/paragraph/table interleaving produces ordered sections and correct citations; merged/nested cells, empty blocks, limits, and repeated parsing remain deterministic.

#### ISS-002-032 — Validate AI semantics before caching success

**Implementation area:** `backend/app/services/analysis/review.py`, AI-run repository.

**Work:** Validate all operation references and semantic invariants before recording reusable success. Retain safe attempt accounting on rejection and allow a later valid attempt. Revalidate cached data against the same acceptance contract; repair incorrect success evidence without inventing a valid response.

**Proof of resolution:** Unknown operation then valid response produces failed/nonreusable then accepted evidence; cached valid response incurs no new provider call; invalid cache does not poison retries.

#### ISS-002-039 — Total remote-fetch deadline

**Implementation area:** `backend/app/clients/http.py`, `core/network_policy.py`, source service.

**Work:** Apply one total deadline over resolution, redirects, retries/backoff, and streamed body reads; bound resolver work and clean responses on cancellation. Preserve DNS pinning, TLS, and per-body limits.

**Proof of resolution:** Stalled DNS, slow-drip body, repeated redirects, retries, and cancellations all terminate within budget with no accepted partial source.

#### ISS-002-040 — Bounded provider response reads

**Implementation area:** `backend/app/clients/http.py`, `clients/ai.py`, AI provider/configuration.

**Work:** Introduce bounded authenticated provider-response streaming in the existing client boundary, with operation-specific catalog/completion/embedding limits. Enforce actual decoded size before parsing and close on all outcomes; do not reuse arbitrary-source auth/policy behavior blindly.

**Proof of resolution:** Large, compressed, missing/understated length responses reject before unbounded allocation; valid supported maxima succeed; failed responses create no success evidence.

#### ISS-002-048 — Accounting for rejected AI attempts

**Implementation area:** `backend/app/providers/ai/openrouter.py`, analysis services and AI-run persistence.

**Work:** Capture provider-supplied usage before output validation; persist attempt identity and aggregate known consumption within existing evidence. Distinguish unknown from zero; deduplicate replayed persistence and cached reuse. Use a precise decimal representation for cost arithmetic, never customer billing.

**Proof of resolution:** Invalid 5-token/0.002 response then valid 10-token/0.003 response totals 15/0.005 exactly; all-failed and unknown-usage attempts remain distinguishable without double counting.

### R-OPS — Operational visibility, bounded reads, and repository housekeeping

**Phase:** IP-2. **Items:** `ISS-002-042`, `ISS-002-044`, `ISS-002-047`, `ISS-002-051`, `ISS-002-052`.

Keep observability bounded and truthful. Repair existing contribution automation only within its intended documented integration; unavailable external configuration is not a code failure to conceal.

#### ISS-002-042 — Bounded administrative reads

**Implementation area:** `backend/app/repositories/users.py`, projects/access/credentials/builds repositories, API/client/UI lists.

**Work:** Add stable bounded pagination to existing routes and update current consumers together. Select summary columns without loading excluded AI response JSON. Avoid summary N+1 queries and silent truncation; retain complete traversal.

**Proof of resolution:** Large records/pages have stable ordering, no gaps/duplicates, bounded queries and memory; frontend reaches required pages and AI summaries never hydrate response bodies.

#### ISS-002-044 — Secret-safe structured logs

**Implementation area:** `backend/app/core/logging.py`, `redaction.py`, service/client emitters.

**Work:** Use controlled event names, typed allowlisted context, safe exception categories and sanitized summaries. Prevent raw headers, URLs with credentials, provider bodies, and exception chains from bypassing the boundary; do not claim regexes can identify every possible secret.

**Proof of resolution:** Sentinel passwords/tokens/query secrets and chained exceptions never reach output; correlation/type information remains; malformed metadata cannot break JSON logging.

#### ISS-002-047 — Existing CLA integration disposition

**Implementation area:** `.github/workflows/cla.yml`, contribution/governance documentation.

**Work:** Replace the existing unconditional placeholder only with a verified supported configured integration. Test verified/unverified/unavailable outcomes using fixtures. Record unavailable service credentials as external input; do not invent a verification provider, bypass existing policy, change licensing, or add new approvals.

**Proof of resolution:** Verified/unverified contributor fixtures, fork events, repeat delivery, and outage return truthful outcomes without executing untrusted PR code with secrets.

#### ISS-002-051 — Lifecycle log correlation

**Implementation area:** `backend/app/core/logging.py`, cleanup/runtime command/admission emitters.

**Work:** Centralize supported safe context keys and retain cleanup job/target, runtime command, and admission attempt correlation with bounded types. Use the same security boundary as ISS-002-044.

**Proof of resolution:** Representative failure logs contain supplied nonsecret correlation IDs and retry fields; unknown/sensitive fields remain excluded.

#### ISS-002-052 — Track authoritative documentation

**Implementation area:** `.gitignore`, contribution/evidence docs.

**Work:** Replace blanket docs exclusion with precise generated-output/cache exclusions. Ensure the new plan/evidence additions are normally tracked without force-add; do not expose secrets or local outputs.

**Proof of resolution:** git check-ignore/status shows a new operational Markdown file, still ignores generated caches/secrets, and preserves existing tracked docs.

## 6. Cross-cutting data, contract, and migration design

All entities below are **proposed changes**, not claims that these names/tables/routes already exist. Inspect the current models and reuse or extend them before creating a new entity. New models are justified only by a distinct domain responsibility, never to shadow an existing one.

### 6.1 Migration work units

| Unit | Canonical change | Upgrade/data treatment | Validation and rollback boundary |
| --- | --- | --- | --- |
| M-01: source identity | Current source-version selection/observation metadata; frozen role/aliases/routing in existing build bindings | Backfill from provable current records. Enforce a same-source pointer using appropriate relational constraints. Preserve original hashes/timestamps and mark unprovable historical inputs explicitly. | Count sources/bindings, validate referential integrity, verify A→B→A. Do not downgrade away newly accepted selection history without restoration or a documented loss decision. |
| M-02: execution ownership | Claim epoch/token and lease metadata in runtime commands/cleanup targets; propagate existing build admission token | Quiesce or deliberately reclaim in-flight work using current recovery semantics. Never make an old queued command authoritative by filling a default owner token. | Pause/reclaim/late-effect tests; stale writes affect zero rows. Code rollback must not run old unfenced workers against new ownership semantics. |
| M-03: consumer policy | Named consumer, credential/IdP binding, operation/resource grants, policy revision | Bind each current token to an explicit consumer and snapshot its existing permitted surface. Do not automatically grant newly added tools on later builds. Preserve token hashes; never recover plaintext. | Existing allowed calls continue under explicit equivalent policy; new/unknown operations deny. Export and revocation revisions agree. |
| M-04: company identity | Corporate issuer/subject mapping and project memberships/capabilities using existing users | Preserve user IDs/audit history; never auto-link by email. Preserve existing installation-admin authority. Make existing builder access an explicit migration record, not an implicit forever-all-projects rule. | Verify no lockout or privilege expansion; session invalidation/role mappings; tested local recovery administrator. |
| M-05: semantic artifacts | Curation, annotations, local discovery metadata, privacy policy identity in current project/build configuration | Hash frozen semantic/executable configuration according to its actual role; historical builds stay unchanged. Regenerate shared schemas and current API client. | Deterministic repeated compilation, schema parity, read-only old artifact availability where actually supported; unsupported formats fail clearly rather than invoking a legacy execution path. |
| M-06: operational evidence | Shared typed event envelope, summary projections, bounded delivery state in existing audit/job infrastructure | Separate durable control-plane events from runtime export observations. Deduplicate by event/attempt identity. Store no raw secrets, full prompts, or hidden reasoning. | Totals/retries/retention match underlying records; explicit data gaps; bounded offline buffers. |
| M-07: workflow extensions | Typed auth, projection, pagination, binary, idempotency, and job descriptors in the shared contract | Extend one manifest/compiler/runtime family with explicit compatibility requirements; do not silently change the meaning of historical artifacts. | Test every producer/consumer pair the project actually supports; publish new builds, not rewritten historical manifests. |

### 6.2 Common migration procedure

Before a schema change, record current Alembic head, affected counts/constraints, backup location and protected key references. Generate the next real revision from the repository's migration chain; never guess a revision ID in this plan. Implement a bounded resumable backfill or maintenance command where a transaction over all records would be unsafe. Define uniqueness, foreign keys, check constraints, and query indexes for the actual access patterns.

Rehearse on both a clean schema and a populated fixture snapshot. Check old queued work, cancelled/failed builds, active deployments, revoked credentials, and historical exports. Do not use drop-and-recreate, automatic table creation, destructive reset, or an untested downgrade as a production migration strategy.

Document which rollback restores the previous application image, which requires database restore, and which is forward-only after new writes. Retain encryption keys needed by recovery backups. Normal immutable project rollback must **never** resurrect revoked tokens or obsolete permissions: combine the selected old executable artifact with currently valid security material.

### 6.3 API and frontend contract discipline

Extend the current `/api/v1` routes, schemas, service/repository boundaries, generated OpenAPI, and typed frontend client together. Paths or commands mentioned for new features are proposed interfaces to reconcile with existing naming conventions, not endpoints claimed to exist. Use existing error envelopes, pagination style, audit correlation, request IDs, and authentication dependencies.

For a security-sensitive mutation, return the persisted object plus requested/effective policy revision or lifecycle status. An HTTP success means intent was accepted, not that asynchronous runtime change already happened. The UI must show pending, failed, and effective states and recover after refresh/retry. Cache keys and invalidation must include project, consumer/principal, artifact, and policy identity where relevant.

Keep browser cookies/CSRF for human sessions. Non-human control-plane credentials in F-010 are a distinct credential type resolved to the same centralized principal/permission checks; they must not introduce a second business API implementation. Runtime consumer credentials never authorize administrative APIs.

### 6.4 Permission model and serving independence

Resolve trusted principal identity from verified transport authentication, not tool arguments or client-selected application names. Compute effective access from explicit project policy and trusted claims. Filter listing/search/schema retrieval/resources consistently, then check authorization again at execution. Unknown classifications cannot enter a read-only preset. Signed or opaque cursors are bound to the current permitted catalog and fail safely when policy/artifact changes.

Publish access policy through the existing hashed deployment-overlay lifecycle. The runtime evaluates the installed revision locally; it does not require the control plane on every request. Consequently revocation is not instantaneous during a broken delivery path: record and expose pending effectiveness, token expiry, delivery errors, and observed stop/replacement. Do not claim global immediate revocation while also promising disconnected serving.

### 6.5 External effects and observability limitations

Fencing prevents stale publication into authoritative state; it does not by itself cancel a request already accepted by Docker or an upstream API. Use exact operation/deployment identities, idempotent reconciliation, and source-supported idempotency to handle uncertain effects. Never promise exactly-once delivery or transactionality across arbitrary external systems.

Optional metrics/audit export must remain bounded and must not silently become a serving dependency. Define buffer capacity, flush deadlines, retention and drop counters. A lossless multi-day audit requirement cannot be claimed from a small memory buffer; record the supported outage envelope and gaps. Technical resource limits are not paid usage quotas.

## 7. IP-3 — Deliver the first complete business integration

Implement named consumers before scoped tool permissions; both must work before the connection center issues usable configurations. Build curation and invocation instrumentation alongside the same canonical tool contract, then complete evaluation against the first task set. This is coordinated work in existing components, not parallel implementations.

**Required vertical journey:** create project → import authoritative sources → select current versions → configure valid upstream credentials → build/validate → create named consumers with distinct access → deploy → connect external MCP client → list/find/call the correct tools → inspect safe invocation evidence → update source → compare/rebuild → rotate/revoke → stop/recover/rollback.

The first package uses F-022 against the current permitted tool catalog. Its discovery-specific evaluation cases become required when F-008 is delivered; do not mark F-008 implemented because an evaluator exists. Likewise a basic dashboard is not proof of every configured exporter, and a successful mock connection is not proof of a named live-client integration.

Use one fixture/customer API and two consumers: read-only reporting and explicitly authorized support writing. Only a designated test account may receive test mutations. When the selected task requires pagination, delegated permissions, data minimization, or a corporate login, bring the corresponding feature forward in dependency order rather than weakening the business/security requirement.

## 8. Feature implementation specifications — all 32 proposals

All cards below are **Planned**. Priority/effort are inherited from `todo_features.md`; S/M/L express relative scope, not a schedule. Each feature requires its specific acceptance cases plus the shared checklist in section 11. Related defect corrections are prerequisites, not additional feature counts. [R2]

### F-002 — Named consumer applications and access lifecycle

**Phase / priority / effort:** IP-3 / P1 / M. **Dependencies:** R-ACCESS and R-WORKERS.

**Business outcome:** Each company assistant or automation has an identifiable owner and credential lifecycle instead of a shared anonymous connection.

**Existing implementation area:** backend MCP access domain/models/repository/service/schemas; existing project credentials/access UI; runtime inbound authentication.

**Data and contracts:** Introduce a project-scoped consumer identity only if no equivalent exists: stable ID, name, purpose, owner/contact, enabled state, credential/verified IdP bindings, timestamps, and policy revision. Existing token rows reference consumers; OIDC bindings use trusted issuer plus application identity, with subject constraints where required. No tenant or paid-seat model.

**Implementation:** Migrate existing tokens to explicit consumer records without changing hashes or exposing plaintext. Resolve the consumer from verified authentication, not a supplied tool argument. Create/disable/rotate/revoke through existing lifecycle commands and audit events. Record last activity from actual bounded runtime observations and label unknown activity explicitly.

**API and UI:** Extend current access screens and routes with paginated consumer summaries, ownership, expiry, and requested/effective runtime state. Expose one-time issuance only; connection templates contain secret placeholders. Idempotent retry must not silently issue a different credential.

**Acceptance:** Two applications remain isolated during rotation/revocation; unknown or disabled bindings fail; pending delivery never appears effective; migrated tokens retain explicit equivalent access; no plaintext appears in list/export/log output.

**Documentation/evidence:** Access model, token migration, ownership/runbook, and consumer lifecycle examples; record live versus fixture verification separately.

### F-001 — Tool-level permissions and read-only consumer profiles

**Phase / priority / effort:** IP-3 / P1 / L. **Dependencies:** F-002; R-ACCESS; M-03.

**Business outcome:** A reporting consumer cannot perform the support application’s write operations or inspect restricted resources.

**Existing implementation area:** packages/contracts manifest/runtime-secret contracts; mcp_runtime auth/inbound.py, server/factory.py, tool/resource registries, executor; backend access service.

**Data and contracts:** Add explicit operation/resource grants and denies, evidence-backed read-only classification, and an installed policy revision in the existing access overlay. Refer to stable operation identities and defined metadata visibility; freeze migrated access to the current operation set rather than auto-granting future tools.

**Implementation:** Retain verified request context instead of discarding it. Use one pure permission evaluator for listing, schema discovery, resource reads, and execution; deny unknowns and recheck each call. Bind caches/cursors to principal, artifact and policy. Read-only presets include only operations explicitly classified as safe; annotations alone are not enforcement. Publish access updates through the existing revisioned lifecycle.

**API and UI:** Add capability-selection and read-only preset controls to consumer configuration with an effective-permission preview. Show why an operation is unavailable without disclosing restricted schema data. Use existing protocol-compatible auth errors and current API validation envelopes.

**Acceptance:** Cross-consumer direct calls, hidden-tool names, resource URIs, pagination cursors, cache reuse, spoofed claims and new source operations cannot broaden access. Authorized writes execute without a human approval step. Test offline serving and delayed revocation honestly.

**Documentation/evidence:** Permission matrix, policy precedence, migration/backward-artifact treatment, revision effectiveness, and negative authorization evidence. Follow the referenced MCP revision and actual SDK behavior. [S1], [S2]

### F-007 — Business-oriented tool curation and annotations

**Phase / priority / effort:** IP-3 / P1 / M. **Dependencies:** R-CONTRACT; frozen source/build identity.

**Business outcome:** Tools use clear business language and valid examples without changing source API execution.

**Existing implementation area:** backend analysis/compilers/build configuration; shared MCPTool; frontend operation details; runtime tool advertisement.

**Data and contracts:** Extend versioned project operation metadata with curated title/description/category, schema-valid examples, optional supported annotations, provenance and override ownership. Keep one stable tool identity; any public rename is an explicit breaking change.

**Implementation:** Merge source semantics, explicit operator overrides, and build-time AI enrichment with deterministic precedence. Do not let AI overwrite explicit curation or infer transport/auth behavior. Emit standard supported annotations only; record source/operator evidence for behavioral hints. Recompute relevant semantic build identity and diff; maintain raw operation coverage.

**API and UI:** Add an operation curation editor with source/generated/curated comparison, schema-valid example checks, reset-to-source behavior, and a clear next-build effect. Use the existing build process to publish.

**Acceptance:** Rebuild preserves overrides; method/path/auth/required fields remain identical; invalid examples fail; annotation and name changes are visible; dangerous/unknown operation classification cannot enter a read-only grant implicitly.

**Documentation/evidence:** Curation precedence, annotation semantics and examples; update generated schemas and document that behavioral hints do not grant authorization. [S2]

### F-005 — Runtime observability and operational service dashboards

**Phase / priority / effort:** IP-3 / P1 / M. **Dependencies:** ISS-002-044 and ISS-002-051; F-002 attribution.

**Business outcome:** Operators distinguish MCP adapter failures from authentication, upstream latency and capacity problems.

**Existing implementation area:** existing backend observability and runtime logging/executor/API client; current project/global operational pages.

**Data and contracts:** Define bounded typed metrics and event context: operation/build/project identity, outcome category, duration distributions, in-flight count, response bytes and known consumer attribution. Put high-cardinality request/user IDs in safe events rather than unrestricted metric labels.

**Implementation:** Instrument the single execution path, distinguishing adapter, upstream, auth-refresh and queue/pool time. Integrate optional OpenTelemetry through a dedicated export client with finite queues/timeouts. Keep a company-controlled collector optional and external; its outage must not break execution. Do not add a second metrics database for identical telemetry.

**API and UI:** Extend existing operational screens with observed rates, error categories, histogram-based latency, and last-observed health. Display no-data/outage windows instead of synthetic zeroes. Initially expose useful summaries and one proven exporter, then document supported exporter configurations.

**Acceptance:** Fixed successes/timeouts/denials produce exact counts; histogram-derived percentiles are correct; collector outage/recovery is bounded; labels remain bounded and secrets/bodies are absent. Measure telemetry overhead under the same load.

**Documentation/evidence:** Metric definitions, exporter configuration, cardinality/retention limits, no-data semantics and measured adapter overhead.

### F-006 — Runtime invocation audit and SIEM export

**Phase / priority / effort:** IP-3 / P1 / M. **Dependencies:** F-002; F-005 event envelope; R-OPS.

**Business outcome:** Security teams can attribute permitted and denied capability calls without collecting raw business payloads.

**Existing implementation area:** runtime auth/server/executor; backend audit and existing job/delivery boundaries; dedicated export client.

**Data and contracts:** Use one event identity and schema with principal/consumer, project/build/policy, operation, timestamps, correlation, authorization result and observed outcome. Separate request acceptance, upstream completion, and unknown outcome. Default to no argument/result body capture.

**Implementation:** Emit safe invocation events once per logical attempt with retry linkage. Export asynchronously to a configured company sink using bounded delivery/retry buffers and explicit gap/drop counters. Retain durable control-plane audit in its existing store; do not require synchronous database writes from disconnected runtimes. Define supported outage capacity rather than claiming unlimited lossless delivery.

**API and UI:** Add permission-filtered audit search/export and delivery status using existing audit patterns. Restrict raw event detail appropriately; lifecycle events distinguish intent from observed enforcement. Do not expose provider error bodies.

**Acceptance:** Allow/deny/timeout/unknown-outcome cases correlate end to end; duplicate delivery is deduplicable; buffer exhaustion is visible; exporter outage does not stop normal serving; retention and secret sentinels are verified.

**Documentation/evidence:** Event schema, customer SIEM configuration, privacy/retention, delivery guarantees and limits; attach a real supported-sink test when available.

### F-009 — Consumer connection center and client configuration export

**Phase / priority / effort:** IP-3 / P1 / S. **Dependencies:** F-001 and F-002; runnable export/deployment foundation.

**Business outcome:** A business application can connect to its permitted project endpoint without reverse-engineering authentication or setup.

**Existing implementation area:** frontend project deployment/access pages and typed clients; backend deployment reads and existing MCP client.

**Data and contracts:** Generate connection metadata from observed deployed hostname, TLS, protocol/auth mode, consumer policy and artifact identity. Client templates have a documented supported client/version and no stored plaintext.

**Implementation:** Provide a bounded non-mutating diagnostic sequence for TLS, authentication, MCP initialization, and permitted listing. Call only configured endpoints using existing URL policy. A setup snippet is not proof that a named client supports it; record actual interoperability. Keep diagnostics separate from deployment execution.

**API and UI:** Add copy/export actions, required environment/secret references, connection-status explanation and specific remediation. Do not include credentials in URLs or persistent browser storage.

**Acceptance:** One actual external client connects using the template; two consumers see different grants; expired credentials and wrong host/TLS explain failure; diagnostics never call business writes.

**Documentation/evidence:** Client/version compatibility table, exact setup steps, expected limitations and secret handling; retain logs/fixture evidence separately from live proof.

### F-022 — Business-scenario and tool-discoverability evaluation

**Phase / priority / effort:** IP-3 / P2 / M. **Dependencies:** F-007; F-001; extend cases when F-008 is delivered.

**Business outcome:** Prove that external consumers can select and use the correct business capability, not just list syntactically valid tools.

**Existing implementation area:** existing validation harness, backend build/review evidence, shared contracts tests and external-client test fixtures.

**Data and contracts:** Add a versioned task dataset: business question, permitted principal, expected operation(s), valid argument constraints, fixture outcome and declared ambiguous/unsupported cases. Associate evaluation results with exact manifest, dataset and optional model/prompt identities.

**Implementation:** Run deterministic mapping/permission/outcome checks in existing test infrastructure. Optional bounded build-time semantic evaluation uses the current AI client and records usage; it does not become a runtime agent. Execute business scenarios only against fixtures or explicitly designated test accounts. Evaluate current catalog selection now and add discovery-specific assertions when supported.

**API and UI:** Expose task accuracy, ambiguity, context bytes, failure classes and build comparison alongside validation evidence. Report structural coverage and task success separately, with denominators and unsupported cases. No universal accuracy or savings claim.

**Acceptance:** Good, ambiguous, forbidden and wrong-tool tasks are distinguished; description regressions are detected; forbidden writes and cross-consumer access always fail; repeated deterministic runs agree; optional model-dependent results remain labelled.

**Documentation/evidence:** Task dataset provenance, evaluation command, expected outputs, selected external client/model, costs and first-workflow scorecard.

### F-003 — Control-plane SSO and identity-provider MFA integration

**Phase / priority / effort:** IP-4 / P1 / M. **Dependencies:** R-ACCESS; retain existing users/sessions.

**Business outcome:** Company users sign in through their corporate identity lifecycle and MFA rather than maintain another unmanaged password.

**Existing implementation area:** backend auth/core/clients, users/sessions repositories, API dependencies and frontend login/auth provider.

**Data and contracts:** Add a unique immutable issuer/subject binding to existing users, trusted provider configuration, short-lived login transaction state, and explicit group mapping metadata. Never create a second user directory or link by unverified email.

**Implementation:** Implement OIDC authorization-code flow with PKCE, state, nonce, exact redirect/issuer/audience validation, single-use callback state and server-side token handling. Retain existing session cookies/CSRF. Apply only explicitly trusted assurance/group claims. Invalidate local sessions on local disable; document the bound for detecting upstream deactivation. Preserve a narrowly controlled audited local recovery administrator.

**API and UI:** Add provider configuration and sign-in/error/recovery paths. Existing-account linking is explicit authenticated administration, not automatic takeover. Store sensitive tokens only where required and encrypted; never in frontend persistent storage.

**Acceptance:** Replay/state/nonce/issuer/audience/redirect attacks fail; group change/deactivation/session expiry obey documented bounds; IdP outage does not permit bypass; recovery admin works without removing MFA policy.

**Documentation/evidence:** SSO setup, claim mapping, session/recovery behavior, and selected-provider live evidence; fixture-only provider testing is not labelled production verification. [S3]

### F-004 — Project-scoped collaboration and read-only audit access

**Phase / priority / effort:** IP-4 / P1 / L. **Dependencies:** existing user authorization; F-003 when IdP groups are used; M-04.

**Business outcome:** Teams administer only their projects and auditors inspect evidence without secret/deployment privileges.

**Existing implementation area:** backend auth dependencies/services/repositories and project aggregate; all project API/event/export paths; React route/menu permissions.

**Data and contracts:** Extend existing principal permissions with project membership and capabilities for view, source changes, build, deploy, credentials, policy and audit. Keep installation administration distinct. Map configured trusted groups to memberships; no organization/workspace tenancy.

**Implementation:** Centralize capability checks and query scoping for list/count/details/download/events/background mutation ownership. UI hiding is not security. Snapshot prior builder access explicitly at migration to preserve known intended access without automatically granting future projects. New project creators receive defined membership; every cross-project lookup verifies association.

**API and UI:** Add membership/capability screens and read-only audit views. Reuse current project pages with disabled actions and explanatory state, not separate copies of each UI/API for every role.

**Acceptance:** Enumerate all routes including counts, exports, events and job reads; team A cannot infer/access team B resources. Viewer cannot mutate. Concurrent membership removal and queued mutation follow documented reauthorization semantics.

**Documentation/evidence:** Permission matrix, migration access report, IdP-group mapping and negative route coverage; never equate inherited broad admin power with ordinary membership.

### F-008 — Bounded, permission-aware runtime tool discovery

**Phase / priority / effort:** IP-4 / P1 / M. **Dependencies:** F-001 and F-007; existing catalog remains canonical.

**Business outcome:** Consumers of large APIs retrieve a small relevant permitted tool/schema set instead of unnecessary catalog context.

**Existing implementation area:** compiler artifact generation; runtime tool registry/server; shared discovery metadata; connection templates/evaluation.

**Data and contracts:** Compile a local lexical index from stable names, curated descriptions, parameter names and synonyms. Include artifact identity, deterministic ranking configuration and byte/result bounds; no runtime model or Milvus dependency.

**Implementation:** Expose ordinary explicitly named discovery/schema tools supported by the existing MCP protocol, not invented protocol methods. Filter permissions before ranking/output and bind cursors/caches to policy. Resolve discovered operation calls through the same executor. Keep standard permitted listing available as supported by the chosen client; do not assume every client can exploit discovery to reduce context.

**API and UI:** Add discovery preview and configured-client guidance to operation/connection views. Explain helper capabilities separately from source-operation coverage; no duplicate aliases for the same HTTP operation.

**Acceptance:** With 1,000 operations, relevance and exact schema correctness meet the fixed task dataset; unauthorized names/schema snippets never leak; output is bounded; Builder Plane outage is irrelevant; context reduction is measured for the actual client.

**Documentation/evidence:** Discovery helper contract, deterministic ranking, client limitations, scoped cursor behavior and F-022 comparison.

### F-012 — Operational rate limits, concurrency controls, and circuit breaking

**Phase / priority / effort:** IP-4 / P1 / M. **Dependencies:** F-002, F-005; bounded runtime execution.

**Business outcome:** A noisy or looping consumer cannot exhaust the project API or starve other permitted callers.

**Existing implementation area:** runtime server/executor/API client; shared policy overlay/config; backend project settings and operations UI.

**Data and contracts:** Configure technical burst/rate and concurrency budgets per supported local consumer/project group, queue wait limits, circuit error policy and total request deadline. These are infrastructure protection values, not billing or entitlements.

**Implementation:** Use bounded local counters/buckets/semaphores in the single serving runtime with a monotonic clock. Apply identity before per-consumer limits; also bound unauthenticated transport work. Propagate one remaining budget across retries and later composite steps. Circuits use narrowly defined transient failures and bounded recovery checks; no mandatory Redis/control-plane call per invocation.

**API and UI:** Expose safe settings validation and operational rejection/recovery metrics. Return protocol-compatible retry guidance without promising a durable global quota across restarts or unsupported multiple runtimes.

**Acceptance:** Burst, sustained load, starvation, request cancellation, runtime restart and upstream failure storms have finite bounds. Different consumers remain isolated; resource return is guaranteed on exceptions; circuits recover deterministically.

**Documentation/evidence:** Limit semantics, restart behavior, supported topology, capacity measurements and retry/circuit definitions.

### F-031 — Build-data privacy controls and processing visibility

**Phase / priority / effort:** IP-4 / P2 / M. **Dependencies:** R-SOURCE; bounded AI client; F-007 semantics.

**Business outcome:** Operators can inspect and minimize which source examples/descriptions/documents leave the company during build intelligence.

**Existing implementation area:** source/build configuration, analysis/retrieval/context assembly, dedicated OpenRouter client, privacy/settings UI.

**Data and contracts:** Add versioned inclusion/exclusion/redaction rules and context identity with source/section attribution. Record permitted processor/model routing configuration and accounting without retaining secrets or hidden reasoning. Executable source fidelity is independent from the semantic context sent externally.

**Implementation:** Apply deterministic minimization before provider requests, build previews from that same normalized context, and include privacy-policy identity in AI reuse decisions. Validate available provider controls against current official docs rather than invent region/retention guarantees. Default exclusion of actual secrets remains mandatory before this feature ships.

**API and UI:** Add a permission-restricted effective-context preview, inclusion explanation and build processing record. Do not require a manual approval click on each build or send excluded data to a different provider as fallback.

**Acceptance:** Sentinel credentials and excluded sections never reach provider fixtures; preview matches transmitted context; policy change invalidates inappropriate reuse; mapping/validation correctness remains; unavailable provider controls fail clearly.

**Documentation/evidence:** External processing boundary, configured controls and their limitations, redaction policy revision, context provenance and accounting; no unsupported compliance claim.

### F-010 — Service-account automation, CLI, and configuration as code

**Phase / priority / effort:** IP-5 / P1 / L. **Dependencies:** F-004; stable source/configuration identity.

**Business outcome:** Platform teams manage installations and projects through existing automation without browser scripting or human passwords.

**Existing implementation area:** backend auth/principal/API services; scripts or existing app CLI package; generated API clients; project settings.

**Data and contracts:** Add non-human principal metadata and scoped hashed credentials using existing credential/auth conventions. Extend audit actor typing deliberately rather than fabricate a human user for a service account. Declarative configuration reconciles into current database state and is not a second authoritative store.

**Implementation:** Provide a small CLI over existing routes for inspect/validate/diff/apply, source import, build, export and explicitly requested deployment/rollback. Normalize semantic configuration and use idempotency keys/expected revisions. Separate dry inspection from mutations; secret values are references and never command output. Use the same central authorization for cookie and service credentials.

**API and UI:** Define proposed commands such as `mcplica project inspect` only after reconciling the existing CLI layout. Return machine-readable output and meaningful exit states for accepted/pending/failed work. UI and CLI observe identical state.

**Acceptance:** Repeated unchanged apply creates no duplicates or unnecessary builds; interrupted accepted commands can be queried/retried idempotently; scope violations fail; a runtime token cannot administer the platform.

**Documentation/evidence:** CLI reference, service credential rotation, configuration schema, examples with no secrets, idempotency/revision semantics and pipeline examples without deployment tests.

### F-011 — Opt-in Git/source synchronization and rebuild automation

**Phase / priority / effort:** IP-5 / P1 / M. **Dependencies:** F-010; ISS-002-001 through ISS-002-003 and bounded fetch fixes.

**Business outcome:** The generated capability follows authoritative API specification changes without manual repeated uploads.

**Existing implementation area:** existing sources/service/HTTP client/jobs; a dedicated Git provider client; source configuration UI.

**Data and contracts:** Add a source synchronization binding with allowed repository/file/ref, resolved immutable commit, last observed content identity, delivery cursor/event ID, and opt-in schedule/rebuild policy. Credentials stay in existing protected credential settings.

**Implementation:** Verify signed webhooks, deduplicate/out-of-order events, and resolve the configured branch/ref to an immutable commit before fetching required source/dependency files. Never execute repository content. Reuse current version selection and build creation; unchanged content does not trigger AI spending. Rebuild is explicit opt-in; deployment is never implied by a webhook.

**API and UI:** Add sync configuration, last success/failure, current revision and update preview. CLI uses the same service. Clear retry/remediation for revoked integration credentials and removed paths.

**Acceptance:** Duplicate/reordered webhooks, branch changes, A→B→A, partial dependency fetch and credential loss preserve consistent source selection; failed sync/build leaves active runtime unchanged; no arbitrary URL/path/code execution.

**Documentation/evidence:** Configured Git provider signature contract, event semantics, schedule bounds, build spending behavior and fixture/live proof per provider.

### F-021 — Consumer impact analysis and deprecation tracking

**Phase / priority / effort:** IP-5 / P2 / M. **Dependencies:** F-002, F-005/F-006, corrected executable diff.

**Business outcome:** API teams know which applications may break before publishing a changed capability.

**Existing implementation area:** existing build diff and operation services; consumer registry/audit summaries; build detail UI.

**Data and contracts:** Classify public tool name/removal, required input, output-schema, auth, behavior and documented deprecation changes by stable identity. Maintain explicit registered dependencies separately from usage observations; absence of recent usage is not proof of no dependency.

**Implementation:** Compute a deterministic compatibility projection from both artifacts, join to bounded observed/declared consumers, and emit an immutable impact report. Preserve unsupported/unknown classifications. Do not serve old/new runtimes side by side or hide breakage through duplicate compatibility tools.

**API and UI:** Show affected consumers/owners with the supporting operation and observation date, severity rationale, and unknown coverage. Export machine-readable impact data for existing CI/notification clients.

**Acceptance:** Known breaking and nonbreaking fixtures classify correctly; source provenance-only changes do not create false breakage; affected/unknown consumers are visible; report generation does not modify deployed artifacts.

**Documentation/evidence:** Compatibility rules, data-window limitations, deprecation notices, and examples connecting exact change evidence to a consumer.

### F-023 — Non-chat API/MCP contract playground

**Phase / priority / effort:** IP-5 / P2 / M. **Dependencies:** F-007; existing validation harness; F-004 permissions.

**Business outcome:** Builders diagnose source-to-tool mappings and serialization without a separate handwritten test client.

**Existing implementation area:** frontend operation/validation pages; existing MCP validation client/harness and request builder.

**Data and contracts:** Define typed saved fixture cases with schema-valid inputs, mock response, expected serialized request and source/artifact identity. Store no real secrets. Preview metadata is not a generated alternative runtime.

**Implementation:** Reuse the same argument validator/request builder with test-only dependency adapters. Default to mock execution; show redacted serialization and response contract validation. A separate explicitly invoked connectivity diagnostic may use only configured non-mutating diagnostic operations. No automatic real writes, chat UI or agent execution backend.

**API and UI:** Add forms for nested/form/multipart data, source/manifest comparison and export of reusable fixture cases. Make mock versus real diagnostic mode unmistakable and keep test adapters out of production dispatch.

**Acceptance:** Inputs serialize identically to runtime fixtures; secret injection is redacted; default playground produces zero upstream business calls; saved cases replay against the existing harness.

**Documentation/evidence:** Playground boundaries, case schema, safe diagnostics and how to convert a reported failure into a regression test.

### F-025 — Lifecycle notifications and operational integrations

**Phase / priority / effort:** IP-5 / P2 / M. **Dependencies:** F-005/F-006 event identity; F-021 for impact events.

**Business outcome:** Operations teams receive actionable source/build/credential/runtime events in their existing systems.

**Existing implementation area:** existing audit/event services and durable job machinery; dedicated bounded HTTP/export client; project settings.

**Data and contracts:** Add notification subscriptions and bounded delivery records attached to canonical events: event ID, destination reference, attempts, due time and last outcome. Secrets/signing keys use existing secret storage. Do not introduce another message broker.

**Implementation:** Deliver signed generic webhooks with bounded retry/backoff and idempotent event IDs. Add destination-specific message templates only for an actually configured supported endpoint. Apply URL/DNS controls on every connect and prevent retry amplification. Notification failure never rolls back the originating valid business/control-plane intent.

**API and UI:** Show subscription filters, last delivery/failure, retry state and safe test-message outcome. Payloads omit credentials, private data and uncontrolled upstream errors.

**Acceptance:** Duplicate deliveries are identifiable; invalid signatures/revoked destinations/SSRF/retry exhaustion are safe; failed notification does not stop unrelated cleanup/builds; expiry events go only to configured recipients.

**Documentation/evidence:** Event/subscription schemas, webhook verification, delivery limits, owner contacts and selected operational integration proof.

### F-014 — Enterprise secrets-manager integration

**Phase / priority / effort:** IP-6 / P2 / M. **Dependencies:** ISS-002-045; secure credential materialization.

**Business outcome:** Companies reference centrally managed secret versions rather than copy every value into application settings.

**Existing implementation area:** existing credential model/services, secret materializer and dedicated client/provider boundary; settings UI.

**Data and contracts:** Extend the current credential origin with mutually exclusive encrypted-inline material or an external provider/path/version reference. Preserve one canonical credential record and AAD/ownership rules. Add per-provider configuration only for a documented supported selected backend.

**Implementation:** Implement a dedicated provider client with authentication, bounded calls, safe errors and version metadata; resolve at authorized materialization/rotation, not every runtime invocation. Rotate through existing observed-effect commands and keep last known configured versus newly resolved states separate. Do not ship a test fake as an active provider.

**API and UI:** Expose provider/reference/version and readiness without revealing resolved values. Allow explicit rotation/check operations subject to existing credential capability. Do not silently use another project’s or local fallback secret.

**Acceptance:** Versioned lookup, expiry, permission denial, provider outage, rotation and worker restart preserve isolation/accurate effect state; exported artifacts/logs contain references only; runtime works from valid mounted material without per-call vault access.

**Documentation/evidence:** Selected-backend setup, least-privilege access, secret-version lifecycle, refresh bounds and live evidence or specific external-input limitation.

### F-015 — Enterprise upstream authentication profiles

**Phase / priority / effort:** IP-6 / P2 / L. **Dependencies:** F-014 when external material is used; shared credential selector.

**Business outcome:** Internal APIs using certificates, signed cloud requests or combined mechanisms can be compiled faithfully.

**Existing implementation area:** shared AuthProfile/RuntimeSecretBundle; backend canonical security/credential selector/compiler; runtime auth manager/pinned HTTP transport.

**Data and contracts:** Add only explicit supported descriptors for mutual TLS/custom CA, SigV4 signing parameters and source-declared AND-groups. Preserve OR-alternative selection semantics. Secret/certificate material stays out of manifests and tool arguments; descriptor constraints prevent conflicting header ownership.

**Implementation:** Extend the same auth-manager/client path for each selected mechanism, sign the final canonical request, validate expiry/CA/host and keep credential refresh policy explicit. AND groups require every member; no downgrade to one easier scheme. Do not implement arbitrary authentication scripts or disable TLS checks. Deliver each provider mechanism completely before claiming support.

**API and UI:** Extend credential forms and source security discovery with accurate required fields and compatibility errors. Existing single-profile artifacts retain their documented meaning or receive an explicit rebuild requirement.

**Acceptance:** Expired/wrong-host certs, invalid CA, wrong signing region/service/body, temporary token expiry, missing AND members and header collisions fail. Valid requests match authoritative provider fixtures and actual selected integration where available.

**Documentation/evidence:** Authentication support matrix, source representation, certificate/temporary-key handling, expiry/recovery, contract compatibility and per-mechanism proof.

### F-013 — Upstream delegated identity through token exchange

**Phase / priority / effort:** IP-6 / P2 / L. **Dependencies:** F-001, F-002, F-006; actual provider exchange capability.

**Business outcome:** Calls preserve upstream end-user permissions instead of running through an elevated shared account.

**Existing implementation area:** runtime verified auth context, existing OAuth client/auth manager; backend auth profile/materialization; shared contracts.

**Data and contracts:** Describe configured issuer, exchange endpoint, allowed upstream audiences/scopes and subject/application binding. Keep the inbound credential only within the request lifetime where needed for exchange; safe principal records/logs must not retain it.

**Implementation:** Exchange only validated MCP-audience credentials through an explicitly trusted IdP for a separate audience-bound upstream token. Support RFC 8693 or a documented provider-specific on-behalf-of contract, not an assumed universal implementation. Partition finite caches by issuer/subject/consumer/audience/scopes. Never pass the MCP bearer directly to a business API or fall back to elevated service credentials. [S1], [S4]

**API and UI:** Expose supported provider setup, intended downstream identity, requested scope and safe failure guidance. No user tokens in tool arguments or browser persistence; no per-call Builder Plane token broker.

**Acceptance:** Two users with different source permissions remain separate; wrong issuer/audience/scope/subject and cache-crossing tests fail; IdP outage returns safe auth failure; raw token never reaches the business API except as a newly issued intended upstream credential.

**Documentation/evidence:** Exact provider contract, exchange/cache lifetime, reauthorization behavior and named live integration evidence; unsupported providers remain explicitly unsupported.

### F-016 — Field-level data minimization and constrained business inputs

**Phase / priority / effort:** IP-6 / P2 / L. **Dependencies:** F-001, F-007; F-013 for user-specific upstream access.

**Business outcome:** Consumers receive only permitted business fields and cannot alter identity-bound business-unit parameters.

**Existing implementation area:** shared manifest policy; compiler schemas; runtime argument validation/request builder/response mapping; operation policy UI.

**Data and contracts:** Define typed explicit input restrictions, trusted identity-to-field bindings and output projections. Preserve the authoritative source schema separately from the published projected schema, with policy/artifact provenance and bounded nested/array traversal.

**Implementation:** Validate identity-bound values before serialization; caller conflicts fail rather than silently broadening. Validate the actual source response first, apply permitted projection, then validate the exposed result. Do not invent/default business data or use post-filtering as a substitute for upstream row authorization. Errors/resource metadata must obey the same disclosure policy.

**API and UI:** Add a policy preview showing removed fields and the resulting schema with precise invalid-rule errors. Keep configuration deterministic and publish through the canonical artifact/policy lifecycle.

**Acceptance:** Forbidden nested/array fields cannot appear in result, error, log or resource data; type/required-field semantics of projected output remain valid; cross-user queries and continuation handles cannot bypass restrictions.

**Documentation/evidence:** Projection/binding semantics, data lineage, upstream authorization boundary, schema examples and leak-negative test results.

### F-017 — Source-declared pagination and bounded collection retrieval

**Phase / priority / effort:** IP-7 / P2 / M. **Dependencies:** F-001; source/request/response contract fixes.

**Business outcome:** Reporting tasks receive complete bounded page sequences rather than mistake the first page for the whole dataset.

**Existing implementation area:** canonical source extensions and compiler; shared pagination descriptor; runtime request/result normalization.

**Data and contracts:** Represent declared cursor/offset/page fields, page-size limits, next-page extraction and stop conditions. Continuation envelopes bind project/consumer/subject, operation, artifact/policy, normalized filters, expiry and page budget; encrypt sensitive upstream continuation data if retained in a client-visible token.

**Implementation:** Return a single bounded page by default with explicit continuation/completeness metadata. Multi-page aggregation is allowed only as an explicit capped mapping. Revalidate each continuation and never turn a response URL into an arbitrary destination; accept only declared same-operation navigation. Prevent repeated-cursor loops and state unsupported snapshot consistency.

**API and UI:** Expose pagination support/limits in operation details, examples and tool output. Show partial/error outcomes explicitly, not a deceptively complete collection.

**Acceptance:** Empty/final pages, cyclic cursors, changing datasets, partial failures, forged/expired/cross-consumer handles and oversized page requests remain bounded; the same filter set produces correct source requests.

**Documentation/evidence:** Supported pagination patterns, continuation lifetime and confidentiality, partial-result contract and dataset consistency limitations.

### F-018 — Binary attachments and report-download support

**Phase / priority / effort:** IP-7 / P2 / L. **Dependencies:** F-001, F-016 where applicable; finite runtime I/O budgets.

**Business outcome:** Business APIs can return invoices, spreadsheets and attachments without oversized encoded context payloads.

**Existing implementation area:** runtime API client/response reader/mapper/resource registry; shared resource/response contract; artifact configuration.

**Data and contracts:** Describe supported binary media, maximum streamed bytes, filename/checksum/provenance and ephemeral resource references. Any temporary runtime content is bounded disposable data, not another authoritative object store.

**Implementation:** Stream declared content into bounded private runtime storage and expose bytes through an authenticated supported resource/download mechanism. Authorize metadata and byte reads by consumer/subject/project; a guessed or copied URI is not permission. Expire/delete on policy/lifetime limits and cleanup on disconnect. Do not fetch arbitrary links from source responses or serve active untrusted content as same-origin HTML.

**API and UI:** Show supported format/size/expiry and safe retrieval instructions. Keep filenames sanitized, content dispositions safe and secrets out of references. State restart behavior clearly.

**Acceptance:** PDF/CSV/XLSX fixture bytes/checksum survive; limits interrupt reads; wrong consumer and expired/restarted resources fail; traversal/content-type tricks cannot expose local files; cleanup returns storage to its bound.

**Documentation/evidence:** Format support, client interoperability, temporary-volume sizing, access/expiry/restart policy and streaming memory measurements.

### F-019 — Source-aware idempotency and actionable error recovery

**Phase / priority / effort:** IP-7 / P2 / M. **Dependencies:** F-005/F-006; canonical source evidence.

**Business outcome:** A retry cannot silently duplicate an order or ticket when the source provides an idempotency mechanism.

**Existing implementation area:** shared request/error mapping; compiler; existing runtime API client/auth/executor; safe response mapper.

**Data and contracts:** Declare source-supported idempotency header/field, key constraints, safe retry conditions, bounded Retry-After interpretation and reconciliation operation if documented. Distinguish succeeded, rejected, retryable and outcome-unknown in the result contract.

**Implementation:** Preserve the same key across permitted retries of one logical request; reject conflicting content/key reuse where the source contract supports detection. Retry only evidence-backed safe cases within the original deadline. Do not add a private duplicate business transaction database or claim exactly-once for sources without support. An ambiguous write timeout returns uncertainty rather than automatic replay.

**API and UI:** Expose safe source error codes and recovery guidance; omit raw provider payloads. Document when the external consumer may retry or explicitly call a source-defined lookup.

**Acceptance:** Lost response with supported idempotency causes one source effect; unsupported write never retries blindly; unsafe Retry-After/backoff is bounded; accepted success is not fabricated from timeout; no sensitive source error leaks.

**Documentation/evidence:** Per-operation idempotency/retry support, uncertainty semantics, test-fixture side-effect counts and provider-specific limitations.

### F-020 — Source-defined long-running operation support

**Phase / priority / effort:** IP-7 / P2 / L. **Dependencies:** F-019, F-001; explicit source submit/status/result/cancel operations.

**Business outcome:** An external consumer can submit and inspect a report/reconciliation job without keeping one MCP call open indefinitely.

**Existing implementation area:** canonical job descriptor/compiler/shared contracts; existing runtime executor and source request mapping.

**Data and contracts:** Bind declared submit/status/result/cancel operations and identifier/identity mapping. Use the source as durable business-job authority; an opaque handle must carry or reference validated scope and expiry, not act as authorization itself.

**Implementation:** Return the source job reference promptly and let the external caller invoke the next supported operation. No autonomous polling service or built-in workflow engine. Preserve uncertain submission results and source idempotency. Do not invent cancellation or assume an SDK experimental task facility is interoperable; add protocol task support only after exact pinned client/SDK validation.

**API and UI:** Advertise supported lifecycle operations, terminal states, expiry and inability to cancel where applicable. Normalize progress only when source-defined; no synthetic percentage or hidden retries.

**Acceptance:** Submission, completion, failure, cancellation/unsupported cancellation, expiry, disconnect, duplicate request and cross-principal job lookup have correct finite behavior; a source job survives runtime restart without a second state machine.

**Documentation/evidence:** Job-state mapping and identity rules, supported protocol/client combinations, uncertainty handling and named source acceptance fixtures.

### F-024 — Private capability catalog and registry-compatible metadata

**Phase / priority / effort:** IP-8 / P2 / M. **Dependencies:** F-004 and F-009.

**Business outcome:** Employees find the company’s available MCP-enabled products, owners and connection instructions without a federation proxy.

**Existing implementation area:** current project listing/domain/UI; deployment/readiness summaries; dedicated registry export client when selected.

**Data and contracts:** Add catalog metadata for business domain, owner/support contact, active endpoint/build, auth requirements and last observed health. Generate metadata conforming to the specifically selected registry schema/version; do not assume one schema fits every private registry.

**Implementation:** Filter project discovery by existing memberships/capabilities and produce versioned exports pointing directly to original project endpoints. Catalog availability must not be required for serving. Public publishing is never a default side effect; private source/spec/hostname information remains private.

**API and UI:** Add a consumer-oriented catalog view reusing existing project data, bounded search and connection export. Do not introduce a second project database or combined cross-project execution endpoint.

**Acceptance:** Unauthorized projects, counts and metadata remain invisible; export validates against the selected registry version and points to actual artifact/endpoint state; offline catalog does not interrupt connected runtimes.

**Documentation/evidence:** Private catalog permissions, selected registry contract, metadata privacy and distribution setup.

### F-026 — Automated backup, restore, and project migration utilities

**Phase / priority / effort:** IP-8 / P2 / M. **Dependencies:** M-01 through applicable later migrations; encryption-key recovery.

**Business outcome:** A company can recover authoritative state or transfer one project between controlled hosts with verified continuity.

**Existing implementation area:** existing storage/database/CLI/deployment services; operations backup/upgrade docs; source/artifact manifests.

**Data and contracts:** Define a consistent backup manifest with database/schema snapshot identity, immutable object hashes, configuration, protected key references, and derived-index rebuild metadata. No plaintext credential bundle in ordinary exports.

**Implementation:** Add bounded operator utilities for consistent capture, verification and restore into an isolated target using existing clients. Preserve IDs for full restore; project transfer uses one explicit remapping table where IDs must change. Disable serving until target routing/current security are valid and coordinate source shutdown before replacement activation. Restore derived indexes from authoritative inputs, not untrusted stale search state.

**API and UI:** Report integrity/missing-key/incompatible-schema problems and resumable progress. Keep source and target lifecycle visible; never advertise two active instances as a migration workaround. Recovery tests run separately from deployment.

**Acceptance:** Restore populated fixtures with revoked credentials, historical builds and pending jobs; hashes/permissions match, old revoked access does not revive, indexes rebuild, and measured recovery objectives are recorded. Missing artifacts/keys fail explicitly.

**Documentation/evidence:** Backup consistency, key escrow references, restore/transfer runbooks, identity remapping, RPO/RTO measurements and rollback boundaries.

### F-027 — Searchable, portable documentation resource bundles

**Phase / priority / effort:** IP-8 / P3 / M. **Dependencies:** F-001 and F-008; F-018 for supported binary content.

**Business outcome:** Consumers retrieve relevant cited documentation while the Builder Plane is unavailable.

**Existing implementation area:** existing artifact packaging/resource compiler; shared resource descriptor; runtime resource registry/local index.

**Data and contracts:** Package immutable hashed document chunks/resources and local text-search metadata as canonical build artifacts rather than inline every large body into every manifest. Keep source version/section/citation and byte bounds.

**Implementation:** Load and verify referenced package content from allowed local mounts; search lexically without runtime Milvus/LLM or arbitrary external fetch. Enforce resource grants before search excerpts/read and keep path resolution safe. Publish a new artifact format with explicit runtime compatibility rather than modify historical package bytes.

**API and UI:** Add documentation search preview and citations resolving to exact installed content. Display unavailable/excluded versus empty text accurately; connection guides name supported resource-capable clients.

**Acceptance:** Large fixture corpus searches offline with bounded memory/result bytes; exact citations resolve; tampering/traversal/restricted-resource searches fail; old artifact identity remains unchanged.

**Documentation/evidence:** Package schema, hash/index verification, local resource limits, citations and upgrade/export support.

### F-028 — Reusable business API configuration blueprints

**Phase / priority / effort:** IP-8 / P3 / M. **Dependencies:** F-007, F-010 and F-022.

**Business outcome:** Repeated support/CRM/inventory/reporting integrations reuse validated configuration and examples, not copied runtime code.

**Existing implementation area:** project configuration import/export, curated metadata/compiler, existing CLI/UI and fixture evaluation.

**Data and contracts:** Define versioned data-only packs with source operation/schema fingerprints, required features, proposed curation/grants, valid examples and acceptance fixtures. No secret values, executable scripts, or presumed named-vendor compatibility.

**Implementation:** Validate a pack against the actual authoritative API, produce a deterministic diff, and apply into current configuration through the same service. Preserve explicit project overrides and historical builds. Installing a pack must not automatically grant new write capabilities to existing consumers or deploy it.

**API and UI:** Expose requirements/mismatches, selected changes and resulting configuration. Keep a pack as reusable input content, not a separate project type or orchestration engine.

**Acceptance:** Matching/mismatching APIs, renamed operations, pack updates and local overrides behave predictably; no invented tool or hidden privilege expansion; accepted examples pass F-022 fixtures.

**Documentation/evidence:** Pack schema, compatibility rules, source/vendor evidence, update semantics and useful business recipes.

### F-029 — Explicitly compiled single-project business task tools

**Phase / priority / effort:** IP-8 / P3 / L. **Dependencies:** F-001, F-007, F-019, F-022; customer-confirmed source workflow.

**Business outcome:** An external client invokes a well-defined bounded business sequence without rebuilding its data bindings each time.

**Existing implementation area:** existing canonical/compiler/shared task mapping; single runtime executor; operation/validation views.

**Data and contracts:** Add an operator-authored acyclic sequential descriptor referencing existing same-project operations, typed output-to-input bindings, total budgets and explicit partial-success/compensation declarations. Keep raw-operation coverage and task-tool coverage separate.

**Implementation:** Compile/validate each step and invoke through the same executor with the original principal and cumulative limits. Recheck each referenced operation’s permission, including ones not visible as a task helper. No loops, arbitrary code, AI-chosen steps, cross-project federation or second workflow engine. Compensation is used only when source-declared and authorized; no cross-API atomicity promise.

**API and UI:** Provide source-backed task definitions and previews of steps, failure outcomes and required permissions. Task definitions become immutable in a new build; no automatic triggers.

**Acceptance:** Success, missing operation, invalid binding, denied child operation, midway failure, timeout and supported compensation behave exactly; repeated effects are not blindly replayed and all completed steps remain attributable.

**Documentation/evidence:** Task descriptor, permission propagation, coverage calculation, partial-success/idempotency limitations and a real chosen business scenario.

### F-030 — Signed project-artifact distribution and verification

**Phase / priority / effort:** IP-8 / P3 / M. **Dependencies:** F-010, F-024; current export integrity; selected signing setup.

**Business outcome:** Companies verify the source/configuration/compiler identity of internally distributed generated capabilities.

**Existing implementation area:** existing project artifacts/checksum/release utilities; dedicated signing/registry client; CLI import/export.

**Data and contracts:** Attach an attestation linking source/configuration hashes, validation evidence, compiler/runtime compatibility and configured signer identity to the exact project artifact digest. This extends project exports, not duplicates existing image-release signing.

**Implementation:** Sign with company-controlled keys through the configured client and verify before trusted import. Canonicalize signed bytes, bound parsing, reject tampering and distinguish offline verification from online signer revocation knowledge. Artifact signing is an automated integrity check, not another human approval process.

**API and UI:** Show digest, signer verification outcome and compatible runtime; store keys/credentials only as protected references. Selected internal registry upload is explicit, never public by default.

**Acceptance:** Valid/tampered/unknown-signer/expired-policy fixtures produce exact outcomes; every resource hash binds; old compatible artifact keeps original evidence while current access policy is not rolled back.

**Documentation/evidence:** Attestation/signing contract, trust material rotation, selected registry workflow, offline limitations and restore verification.

### F-032 — Multilingual business terminology and tool documentation

**Phase / priority / effort:** IP-8 / P3 / M. **Dependencies:** F-007 and F-008.

**Business outcome:** Arabic/English and company-specific vocabulary resolve to the same permitted business operation.

**Existing implementation area:** existing semantic metadata/curation, local discovery compiler, documentation/UI components.

**Data and contracts:** Add locale-tagged descriptions/examples/synonyms with provenance, source-original retention and one stable canonical tool/operation identity. Version terminology with the build, not duplicate executable tools for every language.

**Implementation:** Normalize/search locale text locally; optional translation uses the current build-time AI boundary and never changes transport/schema/auth requirements. Preserve units/date/number semantics and ambiguous terminology explicitly. Keep fallback language deterministic. No runtime translation model.

**API and UI:** Add locale/glossary editing and right-to-left support only in affected views, with keyboard/focus/readability checks. Keep machine parameter names and numeric/date types unchanged unless the actual API changes.

**Acceptance:** Equivalent Arabic/English tasks select the same permitted operation; ambiguity is visible; mixed-script/synonym edge cases are bounded; request serialization is identical across locales; targeted RTL/accessibility checks pass.

**Documentation/evidence:** Locale fallback/glossary ownership, translation provenance, terminology evaluation dataset and unchanged executable semantics.

## 9. Implementation ordering and integration dependencies

### 9.1 Critical dependency chains

- Ownership/locking and security intent: `R-WORKERS → R-ACCESS → F-002 → F-001 → F-006/F-009`.
- Source correctness: `R-SOURCE + R-CONTRACT → F-007 → F-022`; then `F-008 → F-027/F-032` where needed.
- Company operations: `F-004 → F-010 → F-011/F-021/F-025`; F-003 supplies trusted corporate identity when configured, not a second permission model.
- Identity and data protection: `R-ACCESS → F-014/F-015`; `F-001 + F-002 + F-006 → F-013 → identity-dependent F-016`.
- Transactional workflows: `F-019 → F-020/F-029`; F-029 also requires F-001 and F-022 and cannot bypass child-operation checks.
- Portable distribution: `F-024 + valid current artifacts → F-030`; F-026 must cover the actual implemented schemas/secret references, not only the initial ones.

### 9.2 Avoid cyclic implementation dependencies

Named consumers need no tool-search implementation. Tool grants need no SSO provider. Basic invocation metrics need no SIEM account. Deterministic evaluation needs no built-in agent and can evaluate the current catalog before search exists. Configuration-as-code consumes existing services rather than owning them. Delegated identity requires a supported external provider but must not block unrelated service-account-backed fixture workflows.

When an external integration is unavailable, complete its typed contracts, real provider client logic, safe configuration rejection, documentation and fixture tests. Leave the corresponding live acceptance explicitly outstanding. Never substitute a production mock, fake identity or unverified “works with any provider” claim.

### 9.3 Change-unit discipline

Implement one coherent root-cause or capability increment per reviewable change unit. First update pure shared rules, then repositories/services and migrations, then API/runtime producer-consumer pairs, then frontend/evidence. A unit is not complete while a normal supported request can reach an old incompatible interpretation. Remove replaced internal code paths in the same coordinated change; preserve historical *data* without maintaining a second serving implementation.

Changes to a shared function must trigger its callers' tests even if those callers belong to later feature IDs. Record dependency adjustments in this root plan and link evidence once; do not fork another “final plan” or duplicate issue file.

## 10. Required end-to-end and adversarial scenarios

Reuse the existing harness and fixtures. The table is a specification of tests to implement/run during execution, not evidence that they were run while authoring this plan. All critical permission, secret, source-identity, and ownership assertions must be deterministic.

| Case | Scenario | Required assertions |
| --- | --- | --- |
| E2E-01 | Clean company-style installation | Frozen dependencies; correct migration head; distinct public UI/API TLS origins; login/refresh/CSRF/events; unknown hosts rejected; no public database/Redis/Milvus exposure. |
| E2E-02 | First business journey | Source import/build/deploy/client connect; exact permitted tool schema; read-only caller can read and cannot write; writer executes only explicitly permitted source operation in a test account. |
| E2E-03 | Invalid input and source fidelity | Malformed request types return documented validation errors; unsupported source operations are explicit; no AI-invented method/path/host/auth; excluded-operation counts and coverage agree. |
| E2E-04 | Historical source restoration | Upload and fetch A→B→A; selection, conditional-fetch observation, discovery identity and new build use the last accepted content; old builds remain unchanged. |
| E2E-05 | Mutable metadata during queued build | Change primary/alias/routing while queued; worker uses frozen binding; changed discovery causes normal stale-deploy rejection. |
| E2E-06 | Identical documents and cleanup | Two projects/two generations/two source bindings; no vector overwrite; correct retrieved provenance; generation deletion does not affect another scope; cleanup counters finish correctly under concurrency. |
| E2E-07 | Final-token revocation | Revocation intent commits; runtime STOP is durable; zero accepted old-token calls after effectiveness; queue failure remains pending/failed rather than “revoked everywhere.” |
| E2E-08 | Rotation despite source drift | Active build A and pending source B; auth-only rotation refreshes A/current secrets or safely stops, never deploys B or fails solely because B exists. |
| E2E-09 | Cancellation and process death | Cancel during a long stage, heartbeat race and worker death; terminal acknowledgement and captured cleanup; next build allowed; no late stale artifact publication. |
| E2E-10 | Lease reclamation and stale effects | Pause old owner before/after an external effect, reclaim and resume; stale state writes rejected, current deployment not stopped by obsolete intent, uncertain Docker effects reconciled. |
| E2E-11 | Policy/cache/cursor isolation | Hidden tool calls, guessed resources, policy changes, copied cursors and shared caches cannot leak restricted catalog/data or grant new operations. |
| E2E-12 | Failed new build/deployment | Invalid schema/auth/hash/new deployment never replaces healthy execution silently; failure and retained active identity visible; no duplicate active serving route. |
| E2E-13 | Project rollback with current security | Restore prior executable build, retain current token revocations/grants; historical activation proof valid; old secret overlays never re-enable revoked access. |
| E2E-14 | Serving independence | With Builder Plane, OpenRouter and Milvus unavailable, already valid runtime calls work within their actual credential lifetime; optional telemetry outage is bounded and reported. |
| E2E-15 | Resource/dependency exhaustion | Spool saturation, slow DNS/body, Redis blackhole, large/compressed provider response, full artifact disk, slow shutdown and restart remain finite, safe and diagnosable. |
| E2E-16 | Corporate identity/project isolation | IdP negative cases, local recovery, membership removal and audit-only role; every list/count/export/event/download route enforces the same intended project boundary. |
| E2E-17 | Headless source lifecycle | Scoped service principal applies identical configuration twice; no duplicate state; signed duplicated/out-of-order Git events resolve one coherent source snapshot; rebuild only when opted in/materially changed. |
| E2E-18 | Delegation and data minimization | Two upstream end users retain different permissions; exchange audiences/scopes/cache keys correct; restricted nested fields absent from outputs/errors/resources/logs. |
| E2E-19 | Pagination, binary and asynchronous source job | Complete bounded page sequence, valid private download, submit/status/result flow, explicit expiry/cancellation semantics and no foreign consumer job/resource access. |
| E2E-20 | Idempotency and partial effects | A lost response with source-supported key produces one side effect; unsupported ambiguous writes report unknown; composed step failure reports actual completed steps without blind replay. |
| E2E-21 | Backup, transfer and signed import | Consistent authoritative restore, key availability, derived-index rebuild, correct endpoint/ID remapping and current security; tampered/signer-incompatible exports fail. |
| E2E-22 | Accurate usage and telemetry | All known provider attempts accounted once including rejected structured results; unknown cost remains unknown; audit delivery loss/no-data windows are explicit. |
| E2E-23 | Multilingual task quality | Fixed English/Arabic tasks identify the same permitted operation without changing request serialization; ambiguous and unsupported cases remain explicit. |

After each relevant case, assert no secret leakage, no cross-project artifacts, consistent lifecycle state, bounded resource release and stable historical hashes. Failure injection must restore the test environment and preserve diagnostics without real company data.

## 11. Test strategy, commands, and per-item definition of done

### 11.1 Required test layers

| Layer | What belongs here | Execution policy |
| --- | --- | --- |
| Pure unit/contract | Fingerprints, schema traversal, selectors, permission policy, parsing, projection, pagination descriptors, response dispatch, safe errors | Fast targeted cases on every affected correction/capability. |
| Real PostgreSQL | Transactions, locks, uniqueness, cancellation/claim fencing, cleanup counters, migration/backfill consistency | Use actual concurrent transactions; fakes are insufficient to prove these properties. |
| Provider/client contract | Catalog modalities, OIDC/exchange, signing, secrets backends, Git/webhook and telemetry | Controlled protocol fixtures first; separately record live support for each actual selected provider. |
| Runtime/MCP integration | Same factory/executor, permissions, schemas, resources, invalid authentication, lifetime/limits | Official/pinned SDK client plus the selected external application; do not infer interoperability from a direct HTTP smoke test. |
| UI | Affected forms, permissions, error/pending/effective states, pagination, connection setup | Reuse existing tests. Target keyboard/accessibility/RTL only where changed; no unrelated theme redesign/testing. |
| Operational | Production-format Compose, TLS, images, storage ownership, worker crash/restart, restore and outage behavior | Isolated real infrastructure using the canonical code. Never execute against production company mutations. |

### 11.2 Existing commands to reuse

The following are grounded in the baseline Makefile and CI workflow. They are **execution instructions, not commands run in this documentation-only task**. Verify them again after changes and use the repository's actual environment requirements. [R7], [R8]

```bash
# From a clean checkout, using the repository's configured toolchain.
(cd backend && uv sync --frozen --extra dev)
(cd mcp_runtime && uv sync --frozen --extra dev)
(cd frontend && corepack enable && pnpm install --frozen-lockfile)

# Existing root checks; ensure the environment paths match the Makefile.
make lint
make typecheck
make api-contract-check
make test

# Existing frontend integration/build commands.
(cd frontend && pnpm check:api && pnpm check:assets && pnpm build)
(cd frontend && pnpm test:e2e)
```

For a small correction, select the existing/new exact test module or node covering it instead of rerunning every test repeatedly. Record the precise command and exit status in evidence; do not leave a placeholder test selector in a completion record. The Makefile uses explicit `UV_PROJECT_ENVIRONMENT` paths while CI runs within each package; choose one consistent installation/execution recipe rather than mixing virtual environments accidentally.

Migration verification is performed **only with a disposable test database or intentionally selected rehearsal copy**:

```bash
(cd backend && uv run --frozen --extra dev alembic -c ../migrations/alembic.ini upgrade head)
(cd backend && uv run --frozen --extra dev alembic -c ../migrations/alembic.ini check)
```

Verify `DATABASE_URL`/`TEST_DATABASE_URL` before executing those commands. The existing CI has explicit PostgreSQL and Docker integration setup; reuse it for the actual marker/environment combinations rather than guessing them. Format checks, shared-schema generation checks, critical coverage, security scans and broader supported-browser suites remain part of the existing integration/release verification policy. Existing `make api-contract` is a generation command: inspect and commit its intended outputs, then run the check; never treat generation alone as proof of parity.

These checks run in development/CI or a deliberately executed verification workflow. Do not attach them to `compose up`, image entrypoints, migration startup, deployment-worker execution, or production rollout scripts. Existing runtime health/configuration checks remain necessary runtime behavior, not an invitation to add business test execution to deployment.

### 11.3 Common completion checklist

- [ ] Exact issue/feature ID, implementation commit and affected functions/paths are recorded.
- [ ] The current baseline was inspected; the issue is reproduced or its disposition is supported by executable/structural evidence.
- [ ] Root cause is corrected in the existing canonical boundary; replaced duplicate/dead internal code is removed.
- [ ] Database and immutable-artifact changes have explicit migration, backfill, recovery and compatibility treatment.
- [ ] API schemas, generated OpenAPI/client, shared contracts and runtime serialization agree.
- [ ] UI states reflect persisted intent versus observed runtime effect; permissions are enforced server-side.
- [ ] Focused positive/negative/regression and relevant integration tests pass; a mock-only result is not presented as live evidence.
- [ ] Failed, cancelled, timeout, stale-owner, duplicate-request and replay scenarios relevant to the item are covered.
- [ ] Credentials, business payloads and hidden model reasoning are not leaked into outputs/logs/reports.
- [ ] Resource limits and cleanup are explicit; no unbounded retries, queues, response reads or schema traversal were added.
- [ ] Existing architecture/product constraints remain true, including one execution path and no runtime AI dependency.
- [ ] Source register and affected owner/operational documentation describe the actual final state.
- [ ] Remaining external limitations are named with their exact unverified acceptance case; no invented completion percentage.

## 12. IP-9 — Operating evidence, adoption, and commercial readiness

### 12.1 Measure, do not invent, the operating envelope

Capture the exact commit, dependency/image digests, host CPU/memory/storage, network setup, source sizes, consumer mix, tool count, payload sizes, test duration/sample count, model configuration and whether caches were cold or warm. Separate MCP adapter time from upstream/API/IdP time. Show distributions rather than average-only summaries.

| Measurement | Required method/output |
| --- | --- |
| Installation friction | A second operator follows the documentation on a clean host; record failed steps, undocumented actions, elapsed setup and first successful external-client connection. |
| Runtime overhead | Run representative JSON operations with a controlled upstream and actual public request path; measure adapter p50/p95/p99 separately. The product's stated p95-below-100-ms objective is a target under its stated assumptions, not a result asserted here. |
| Scale/capacity | Rehearse the stated targets of 100 projects, 1,000 operations/project and 10,000 documentation chunks/project, subject to actual manifest limits and host sizing. Record memory, storage, compile/index behavior and supported combinations. |
| Concurrency/fairness | Increase load across defined consumer groups; measure tail latency, rejection and in-flight bounds. State where the single-runtime topology saturates rather than introduce automatic replicas as a workaround. |
| Build economics | Record initial versus incremental build usage, cached embeddings, retries and known cost. Include rejected attempts; never assume unreported usage is zero. No customer billing system. |
| Tool usability | Fixed task set with expected operations, valid arguments and business outcomes; separate deterministic fidelity, permission correctness and optional model-dependent selection metrics. |
| Failure recovery | Worker death, Redis/IdP/provider/collector outage, full disk and late external effects; record pending/effective states and actual recovery time. |
| Backup/recovery | Verify authoritative data, secrets/key references, derived indexes and authenticated runtime after restore; measure RPO/RTO against the company's stated objectives when available. |

The scale and latency objectives above come from the existing requirements, not independent benchmark results. Do not extrapolate them into an enterprise SLA or claim every arbitrary API is supported. [R5]

### 12.2 Validate with a small number of design partners

Seek two or three companies around the same initial API-exposure problem; this is a proposed validation cohort, not existing customer evidence. Record the buyer, installer, API owner, consuming application, pain point, alternatives actually evaluated, and willingness to contribute access/engineering time or purchase the documented services scope.

Use the same canonical implementation and source-backed configuration, not customer forks. Begin with installation and permitted read workflows; add test-account writes only when required and safely scoped. Capture failures, task-completion results, unsupported source patterns and update/recovery work. Feedback changes priority with recorded reasoning; it does not authorize unsupported executable mappings or erase unfinished backlog items.

Compare against one relevant alternative on the same source/task set only when the company actually considers it. Measure setup/customization effort, source fidelity, task correctness, update effort and operating requirements. Do not reuse vendor marketing as a performance baseline or fabricate a competitive win.

### 12.3 Package a bounded commercial service

Prepare an offer for one company API integration: compatibility assessment, self-hosted installation, explicit consumer access, agreed acceptance scenarios, operator handover, known limitations and a stated support scope. Keep pricing/budget inputs as externally supplied decisions, not invented figures. Sponsorship/support/consulting remain outside runtime feature enforcement under the existing open-source model documented in the feature backlog and owner specification. [R2], [R9]

Define what is excluded: arbitrary unsupported API formats, unlimited customization, autonomous business actions, unspecified IdPs/clients, zero-downtime guarantees not demonstrated, and compliance certification not actually obtained. Produce support/incident contacts, reproducible diagnostics and recovery instructions before claiming an operational service level.

## 13. Execution tracking and evidence protocol

### 13.1 Status vocabulary

| Status | Meaning |
| --- | --- |
| Planned | Described but not implemented/verified. This is every task's status at document creation. |
| Verifying | Reproduction/current implementation inspection is underway. |
| In progress | Confirmed repository work is being implemented; not completed. |
| Verified fixed | A reproduced issue is corrected and its relevant acceptance evidence passes. |
| Verified already satisfied | Current implementation meets the requirement without another code change; link exact evidence. |
| Not applicable—evidence | A finding's precondition/claim is disproved for the recorded implementation; retain the ID and explanation. |
| Awaiting external input | Repository work or live validation needs named provider/client/customer configuration that is unavailable. Not complete. |
| Blocked—technical evidence | An identified technical dependency prevents completion; record failure, owner area and next corrective task. Not complete. |
| Verified feature | The feature's specified delivered scope, negative cases and integration evidence pass; list supported providers/clients and remaining exclusions. |

Store each evidence record with ID, execution SHA, source baseline, reproduction or acceptance case, actual test command and result, changed files/migration revision, artifact/dataset identities, live-versus-fixture label, limitations and verification date. Capture meaningful bounded logs, not secrets or full company records. A checkbox needs evidence, not a narrative assertion.

Update the five existing issue fields without inventing a sixth per-issue schema: link disposition/evidence from its Testing & Validation field or the existing register summary. Update feature status in `todo_features.md` only for the verified delivered scope. Keep this plan's dependencies and next-task pointers current without duplicating detailed test output.

### 13.2 Full issue traceability

Every repository issue has one primary correction package; secondary shared-component impacts are tested through the package/cross-feature dependencies. Initial status is Planned for all rows.

| Finding | Source criticality | Primary package | Phase |
| --- | --- | --- | --- |
| ISS-002-001 | High | R-SOURCE | IP-1 |
| ISS-002-002 | High | R-SOURCE | IP-1 |
| ISS-002-003 | High | R-SOURCE | IP-1 |
| ISS-002-004 | High | R-ACCESS | IP-1 |
| ISS-002-005 | High | R-ACCESS | IP-1 |
| ISS-002-006 | High | R-ACCESS | IP-1 |
| ISS-002-007 | High | R-WORKERS | IP-1 |
| ISS-002-008 | High | R-WORKERS | IP-1 |
| ISS-002-009 | High | R-WORKERS | IP-1 |
| ISS-002-010 | High | R-DEPLOY | IP-2 |
| ISS-002-011 | High | R-DEPLOY | IP-2 |
| ISS-002-012 | High | R-DEPLOY | IP-2 |
| ISS-002-013 | High | R-SOURCE | IP-1 |
| ISS-002-014 | High | R-DEPLOY | IP-2 |
| ISS-002-015 | Medium | R-WORKERS | IP-1 |
| ISS-002-016 | Medium | R-DEPLOY | IP-2 |
| ISS-002-017 | Medium | R-DEPLOY | IP-2 |
| ISS-002-018 | Medium | R-DEPLOY | IP-2 |
| ISS-002-019 | Medium | R-CONTRACT | IP-2 |
| ISS-002-020 | Medium | R-CONTRACT | IP-2 |
| ISS-002-021 | Medium | R-CONTRACT | IP-2 |
| ISS-002-022 | Medium | R-ACCESS | IP-1 |
| ISS-002-023 | Medium | R-CONTRACT | IP-2 |
| ISS-002-024 | Medium | R-CONTRACT | IP-2 |
| ISS-002-025 | Medium | R-CONTRACT | IP-2 |
| ISS-002-026 | Medium | R-CONTRACT | IP-2 |
| ISS-002-027 | Medium | R-CONTRACT | IP-2 |
| ISS-002-028 | Medium | R-CONTRACT | IP-2 |
| ISS-002-029 | Medium | R-ACCESS | IP-1 |
| ISS-002-030 | Medium | R-CONTRACT | IP-2 |
| ISS-002-031 | Medium | R-SOURCE | IP-1 |
| ISS-002-032 | Medium | R-CONTRACT | IP-2 |
| ISS-002-033 | Medium | R-SOURCE | IP-1 |
| ISS-002-034 | Medium | R-WORKERS | IP-1 |
| ISS-002-035 | Medium | R-WORKERS | IP-1 |
| ISS-002-036 | Medium | R-WORKERS | IP-1 |
| ISS-002-037 | Medium | R-WORKERS | IP-1 |
| ISS-002-038 | Medium | R-WORKERS | IP-1 |
| ISS-002-039 | Medium | R-CONTRACT | IP-2 |
| ISS-002-040 | Medium | R-CONTRACT | IP-2 |
| ISS-002-041 | Medium | R-ACCESS | IP-1 |
| ISS-002-042 | Medium | R-OPS | IP-2 |
| ISS-002-043 | Medium | R-DEPLOY | IP-2 |
| ISS-002-044 | Medium | R-OPS | IP-2 |
| ISS-002-045 | Medium | R-ACCESS | IP-1 |
| ISS-002-046 | Medium | R-WORKERS | IP-1 |
| ISS-002-047 | Medium | R-OPS | IP-2 |
| ISS-002-048 | Medium | R-CONTRACT | IP-2 |
| ISS-002-049 | Low | R-ACCESS | IP-1 |
| ISS-002-050 | Low | R-ACCESS | IP-1 |
| ISS-002-051 | Low | R-OPS | IP-2 |
| ISS-002-052 | Low | R-OPS | IP-2 |
| ISS-002-053 | Low | R-DEPLOY | IP-2 |
| ISS-002-054 | Low | R-DEPLOY | IP-2 |
| ISS-002-055 | Low | R-DEPLOY | IP-2 |

### 13.3 Full feature traceability

Every proposal has one detailed implementation card in section 8 and one primary delivery phase. Initial status is Planned for all rows. Bringing a dependency into the first integration changes sequence, not the requirement's identity or a false completion claim.

| Feature | Original priority | Relative effort | Primary phase |
| --- | --- | --- | --- |
| F-001 | P1 | L | IP-3 |
| F-002 | P1 | M | IP-3 |
| F-003 | P1 | M | IP-4 |
| F-004 | P1 | L | IP-4 |
| F-005 | P1 | M | IP-3 |
| F-006 | P1 | M | IP-3 |
| F-007 | P1 | M | IP-3 |
| F-008 | P1 | M | IP-4 |
| F-009 | P1 | S | IP-3 |
| F-010 | P1 | L | IP-5 |
| F-011 | P1 | M | IP-5 |
| F-012 | P1 | M | IP-4 |
| F-013 | P2 | L | IP-6 |
| F-014 | P2 | M | IP-6 |
| F-015 | P2 | L | IP-6 |
| F-016 | P2 | L | IP-6 |
| F-017 | P2 | M | IP-7 |
| F-018 | P2 | L | IP-7 |
| F-019 | P2 | M | IP-7 |
| F-020 | P2 | L | IP-7 |
| F-021 | P2 | M | IP-5 |
| F-022 | P2 | M | IP-3 |
| F-023 | P2 | M | IP-5 |
| F-024 | P2 | M | IP-8 |
| F-025 | P2 | M | IP-5 |
| F-026 | P2 | M | IP-8 |
| F-027 | P3 | M | IP-8 |
| F-028 | P3 | M | IP-8 |
| F-029 | P3 | L | IP-8 |
| F-030 | P3 | M | IP-8 |
| F-031 | P2 | M | IP-4 |
| F-032 | P3 | M | IP-8 |

### 13.4 Documentation updates required during implementation

Update only affected documents, but omit none that would misdescribe the change: the owner product/architecture/design specifications; existing roadmap link; API/manifest/resource schemas and generated clients; configuration/default-variable documentation; installation/TLS/permissions; source/build identity; credential/SSO/policy lifecycle; backup/key recovery; failure/remediation; selected provider/client support; source registers; and release evidence.

This plan's creation does not modify those other files. Later agents must not assume the documentation migration or code work already happened merely because a task is written here. Do not overwrite historic evidence with new results at a different SHA; append the new verification identity and correct stale claims visibly.

## 14. Completion and handover

**Foundation handover:** Every ISS-002 item has an honest disposition and linked evidence; all confirmed code-controlled defects in delivered scope are resolved; external limitations remain visible. No reproduced High failure is ignored simply to proceed with a feature. Medium and Low findings retain their execution tasks and are not silently omitted.

**First-integration handover:** The selected business journey, two consumer permission profiles, task evaluation, actual client connection, source update, revocation and recovery are proven. The operator can explain exact installed artifact/security identities, external processing boundary, supported API/client combinations, and known limits. No demo-only or production fake path is left behind.

**Complete-backlog handover:** Every feature actually delivered has its acceptance evidence, migrations, current contract/UI/docs and supported integration matrix. An intentionally not-yet-built proposal remains Planned, never marked complete because the first integration succeeded. Completion of all 32 means all 32 specified scopes were actually implemented and verified.

**Repository handover:** Final code changes have exact commit(s), source-register dispositions, migration/rollback instructions, generated-contract parity, required test evidence and updated existing release checklist. Record only checklist items that were actually verified; do not invent new approval gates or add testing to production deployment.

### Immediate next execution action

Start IP-0 on current `master`, reproduce the source/access/ownership failure cases, and implement the connected IP-1 corrections with their shared migration/lock-order design. Do not start by generating another audit backlog, replacing the runtime framework, implementing all optional integrations at once, or asking an AI model to infer missing executable API behavior.

## 15. References and verified planning inputs

Repository links are pinned to the planning commit. Paths elsewhere in the plan identify implementation targets and proposed changes; they do not claim a new file/class/route already exists. Public standards links identify the explicit revision consulted, not a promise that every later draft is implemented. Competitor-derived ideas remain documented in `todo_features.md`; they were not newly benchmarked for this plan.

[R1]: https://github.com/yazeedhasan97/MCPlica/blob/aac31ef30edf178587cab7234f173cec322a14a9/issues_002.md
[R2]: https://github.com/yazeedhasan97/MCPlica/blob/aac31ef30edf178587cab7234f173cec322a14a9/todo_features.md
[R3]: https://github.com/yazeedhasan97/MCPlica/blob/aac31ef30edf178587cab7234f173cec322a14a9/docs/implementation_plan.md
[R4]: https://github.com/yazeedhasan97/MCPlica/blob/aac31ef30edf178587cab7234f173cec322a14a9/docs/architecture.md
[R5]: https://github.com/yazeedhasan97/MCPlica/blob/aac31ef30edf178587cab7234f173cec322a14a9/docs/product_requirements.md
[R6]: https://github.com/yazeedhasan97/MCPlica/blob/aac31ef30edf178587cab7234f173cec322a14a9/docs/release/release-checklist.md
[R7]: https://github.com/yazeedhasan97/MCPlica/blob/aac31ef30edf178587cab7234f173cec322a14a9/Makefile
[R8]: https://github.com/yazeedhasan97/MCPlica/blob/aac31ef30edf178587cab7234f173cec322a14a9/.github/workflows/ci.yml
[S1]: https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
[S2]: https://modelcontextprotocol.io/specification/2025-11-25/server/tools
[S3]: https://openid.net/specs/openid-connect-core-1_0.html
[S4]: https://www.rfc-editor.org/rfc/rfc8693

[R9]: https://github.com/yazeedhasan97/MCPlica/blob/aac31ef30edf178587cab7234f173cec322a14a9/docs/open_source_and_sponsorship_model.md
