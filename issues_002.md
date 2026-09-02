# MCPlica — issues_002

Repository: `yazeedhasan97/MCPlica`  
Branch examined: `master`; post-closure verification branch: `release/v1.0.0-preparation`
- Finding evidence baseline: `090ec0a82bf6689c9764716afdd20409c366d178` (commit dated 2026-08-27; branch rechecked on 2026-09-01)
- Implementation review baseline: `708401dc47a7684c8c95ab0e4061d595657c57dc`
- Final code and repository-validation baseline: `801f0ee57e0ed73bf7feeb85649a5ca9b6014c1a`
- Report date: 2026-09-01; implementation closure: 2026-09-02
Task scope: reproduce and disposition every finding, implement every applicable correction, and validate the integrated repository/runtime result.

## Scope and evidence boundary

The original report consolidated evidence-backed findings from the available source examination; it did not claim an every-file audit or that no unlisted issue existed. The 2026-09-02 closure separately rechecked all 55 registered findings against the implementation baseline, reproduced each cited contract or failure scenario, retained 12 corrections already present, and implemented the other 43. The final validation record is authoritative in [`docs/evidence/issues-002-closure.md`](docs/evidence/issues-002-closure.md). No unlisted-file completeness claim or external production-deployment claim is added by this closure.

Repository links are pinned to the evidence baseline. Function names and explicitly described code areas locate evidence where line-numbered excerpts were not available. Findings distinguish source-demonstrated failure paths from explicitly labeled hardening or maintainability gaps. Severity describes impact and preconditions, not an assertion of observed production exploitation. Unverified possibilities and intentional product limitations without a demonstrated defect are not promoted to findings.

All remediation is to the existing canonical clients, shared contracts, services, repositories, and monorepo packages. Preserve authentication/authorization and data integrity. Do not add V2 APIs, duplicate implementations or persistence, parallel execution paths, staging-specific behavior, shadow/canary flows, approval/authority gates, or a replacement architecture. Make required migrations production-safe; update affected schemas and operational documentation as part of later implementation. Apply focused TDD/BDD regression cases before corrections and validate the actual affected boundaries without adding tests to deployment.

## Findings summary

| Criticality | Count |
| --- | ---: |
| Critical | 0 |
| High | 14 |
| Medium | 34 |
| Low | 7 |
| **Total** | **55** |

No Critical severity is assigned from the evidence available; this is not a statement that the unreviewed repository contains no critical defects.

## Verified disposition (2026-09-02)

All 55 findings are closed in repository scope: 12 were already remediated at the implementation
baseline and were explicitly re-verified; 43 remained applicable and were fixed. None was dismissed
as inapplicable and none remains open. Detailed code, schema, test, runtime, and command evidence is
in [`docs/evidence/issues-002-closure.md`](docs/evidence/issues-002-closure.md).

The release-branch revalidation repeated the source, schema, migration, contract, component,
PostgreSQL, Linux-container, Compose, browser, and security boundaries. It also exposed and fixed
four defects in the canonical validation path: the root Make target now loads the backend pytest
configuration explicitly, Ruff classifies repository scripts consistently, the source manifest
hashes canonical Git index blobs on every platform, and documentation validation reads only tracked
Markdown. Focused repository-policy regressions cover each correction.

| Finding | Baseline status | Verified final disposition and evidence |
| --- | --- | --- |
| `ISS-002-001` | Already fixed | Closed; scoped chunk identity and cross-project/generation/source tests. |
| `ISS-002-002` | Applicable | Closed by migration `0021` current-version selection and A-B-A PostgreSQL coverage. |
| `ISS-002-003` | Applicable | Closed by frozen Build/source metadata, trustworthy-history gate, and canonicalization/fingerprint tests. |
| `ISS-002-004` | Applicable | Closed by transition-aware stop-first conflict handling and ordered command tests. |
| `ISS-002-005` | Applicable | Closed by final-verifier durable STOP behavior and idempotency/effect-state tests. |
| `ISS-002-006` | Applicable | Closed by exact-active-Build `security_refresh` intent and stale-source tests. |
| `ISS-002-007` | Applicable | Closed by live/dead-owner cancellation acknowledgement and recovery tests. |
| `ISS-002-008` | Applicable | Closed by admission-token fencing, deadline heartbeat, migration `0025`, and stale-writer tests. |
| `ISS-002-009` | Applicable | Closed by migration `0022` execution tokens/renewal/project lock and reclaim tests. |
| `ISS-002-010` | Already fixed | Closed; distinct UI/API hosts are allowed exactly and unrelated hosts remain rejected. |
| `ISS-002-011` | Already fixed | Closed; exported production Compose requires auth-overlay digest and allowed origin. |
| `ISS-002-012` | Applicable | Closed; OpenRouter catalog includes embedding-capable models and has provider tests. |
| `ISS-002-013` | Already fixed | Closed; canonicalization does not load documentation bodies and has read-boundary tests. |
| `ISS-002-014` | Already fixed | Closed; long-running Compose services restart and one-shot jobs do not. |
| `ISS-002-015` | Applicable | Closed; project-first deployment locking and PostgreSQL serialization are verified. |
| `ISS-002-016` | Applicable | Closed; ASGI/proxy/spool capacity limits align and boundary tests pass. |
| `ISS-002-017` | Already fixed | Closed; API startup remains independent of a live Milvus connection. |
| `ISS-002-018` | Already fixed | Closed; shipped UID/GID is fixed and runtime-init rejects identity drift. |
| `ISS-002-019` | Already fixed | Closed; non-string exclusion inputs return controlled validation errors. |
| `ISS-002-020` | Applicable | Closed; required operational settings reject explicit null. |
| `ISS-002-021` | Applicable | Closed; cleared model settings remain cleared without environment resurrection. |
| `ISS-002-022` | Applicable | Closed; credential writes use the runtime transport/header contract. |
| `ISS-002-023` | Applicable | Closed; exclusions are applied consistently before readiness and compilation. |
| `ISS-002-024` | Applicable | Closed; one shared deterministic auth-selection engine owns readiness and compilation. |
| `ISS-002-025` | Applicable | Closed; shared path parsing supports embedded/multiple placeholders. |
| `ISS-002-026` | Applicable | Closed; schema rewriting is restricted to schema-keyword locations. |
| `ISS-002-027` | Applicable | Closed; JSON Pointer traversal supports arrays and controlled invalid-index errors. |
| `ISS-002-028` | Already fixed | Closed; an exact response cannot fall through to a less-specific media contract. |
| `ISS-002-029` | Applicable | Closed; OIDC issuer identity, including trailing slash, is preserved exactly. |
| `ISS-002-030` | Applicable | Closed; DOCX paragraph/table order and heading context are preserved. |
| `ISS-002-031` | Applicable | Closed; warning/info snapshots remain visible and blocking errors retain context. |
| `ISS-002-032` | Applicable | Closed; invalid AI responses cannot become successful cache entries. |
| `ISS-002-033` | Applicable | Closed; diffs compare effective servers/security and ignore provenance-only churn. |
| `ISS-002-034` | Applicable | Closed; cleanup aggregate updates serialize parent-first under concurrent completion. |
| `ISS-002-035` | Applicable | Closed by migration `0024`, just-in-time claims, and exact attempt fencing. |
| `ISS-002-036` | Applicable | Closed; retention failures are isolated and do not block due cleanup. |
| `ISS-002-037` | Applicable | Closed; acquisition and shutdown attempt every close within bounded deadlines. |
| `ISS-002-038` | Applicable | Closed; Redis/RQ clients have explicit connect and operation deadlines. |
| `ISS-002-039` | Applicable | Closed; one total remote-fetch deadline covers resolution through body streaming. |
| `ISS-002-040` | Applicable | Closed; OpenRouter bodies are stream-limited before buffering/decoding. |
| `ISS-002-041` | Applicable | Closed; password hashing/verifying runs off-loop with admin serialization retained. |
| `ISS-002-042` | Applicable | Closed; management collections use bounded stable pagination and frontend all-page reads. |
| `ISS-002-043` | Applicable | Closed; storage health proves write, flush/fsync, and delete. |
| `ISS-002-044` | Applicable | Closed; central logging allowlists safe data and omits raw sensitive messages/exceptions. |
| `ISS-002-045` | Applicable | Closed; versioned key ring plus transactional re-encryption CLI/service supports rotation. |
| `ISS-002-046` | Applicable | Closed; trusted activation proof cannot be replaced by weaker post-activation evidence. |
| `ISS-002-047` | Applicable | Closed; CLA workflow consumes a configured external status/check and fails unavailable separately. |
| `ISS-002-048` | Applicable | Closed; all structured attempts contribute outcome, token, and cost evidence exactly once. |
| `ISS-002-049` | Applicable | Closed; the last-admin rule counts active administrators only. |
| `ISS-002-050` | Applicable | Closed; OAuth expiry accepts only finite positive numeric values, never booleans. |
| `ISS-002-051` | Applicable | Closed; safe lifecycle correlation fields survive structured JSON formatting. |
| `ISS-002-052` | Already fixed | Closed; authoritative `docs/` additions are visible to Git. |
| `ISS-002-053` | Applicable | Closed; deterministic tracked-source manifest generation/check replaces stale inventory. |
| `ISS-002-054` | Already fixed | Closed; runtime build delegates to Compose and uses its configured image reference. |
| `ISS-002-055` | Already fixed | Closed; the example has one runtime-version assignment and a uniqueness test. |

## Findings

### ISS-002-001 — Documentation vector primary keys collide across projects, generations, and source bindings

1. **Description** — Document chunk identity contains the source content hash, normalized section path, ordinal, and text hash, but omits project, generation, and source-version identity. Collections are shared by embedding dimension and use chunk_id as their primary key. Reindexing identical documentation can overwrite another generation or project’s row, including its ownership metadata. Scoped search then loses previously indexed content; this is an overwrite/isolation defect, not evidence that the search filter itself discloses another project’s results.

2. **Location & Evidence** — [`backend/app/parsers/documentation/chunker.py`][src-001] — chunk_document() identity construction; [`backend/app/clients/vector.py`][src-002] — create_collection(), primary_field_name="chunk_id"; [`backend/app/providers/milvus.py`][src-003] — collection_name(), upsert_chunks(), search(), delete_generation().

3. **Criticality** — **High** — Ordinary rebuilds or shared documentation can corrupt retrieval availability and generation isolation.

4. **Recommended Solution** — Make the existing chunk identity unique to its project, generation, and source-version binding while retaining content_sha256 as the embedding-cache reuse key. Reconcile chunk manifests, retrieval references, provenance, and generation cleanup with that identity. Rebuild affected derived indexes from retained sources through the existing indexing service; do not introduce a second vector store or serving path.

5. **Testing & Validation** — Index identical bytes and headings in two projects, two generations of one project, and two source bindings. Assert distinct stored row identities, correct per-scope counts and searches, unchanged results for the earlier generation, and cleanup that removes only its specified generation. Repeat the same generation upsert and assert idempotency.

---

### ISS-002-002 — Restoring earlier source content does not make it the current source version

1. **Description** — Version persistence deduplicates against every historical content hash and returns the original record without updating a current-version selection. Consumers choose the latest version by creation time. Consequently, uploading or fetching A, then B, then A reports A as the accepted result while subsequent build discovery can still select B. Conditional-fetch metadata also remains attached to the historical record rather than the latest observation.

2. **Location & Evidence** — [`backend/app/services/sources.py`][src-004] — _persist_version(), latest_version(), refresh(); [`backend/app/repositories/sources.py`][src-005] — get_version_by_hash(), latest_version(), latest_bound_versions(); [`backend/app/models/source.py`][src-006] — SourceVersion uniqueness on source_id/content_sha256.

3. **Criticality** — **High** — The system can build and deploy different content from the content the operator just restored.

4. **Recommended Solution** — Represent current selection explicitly in the existing source model, referencing the immutable deduplicated version. Update selection transactionally on every accepted observation, including historical-content reuse. Make discovery, summaries, build binding, retention protection, and HTTP validators use that selection. Preserve immutable version timestamps and historical build bindings; record restoration/selection changes in the existing audit ledger.

5. **Testing & Validation** — Exercise upload and URL refresh sequences A→B→A and A→A. Assert current selection, source summary, discovery fingerprint, and newly created build all reference the last accepted content. Verify historical builds remain unchanged, repeat requests are idempotent, current content survives retention, and 304 handling uses the current observation’s validators.

6. **Resolution (2026-09-02)** — **Closed.** Migration `0021` adds an explicit same-source `current_version_id` selection plus observation timestamp/validator metadata and backfills the latest known version without inventing lost restoration history. Every accepted observation now selects its immutable version transactionally under the source/project lock, records `source.version_selected`, and all summary, discovery, build-binding, validator, and retention consumers use that selection. PostgreSQL regressions cover A→B→A hash reuse, repeated observations, 304 validators, concurrent commit order, frozen historical bindings, and retention. See [`docs/evidence/issues-002-foundation-closure.md`](docs/evidence/issues-002-foundation-closure.md).

---

### ISS-002-003 — Executable build identity does not freeze primary-source and dependency-alias metadata

1. **Description** — The configuration hash covers source-version IDs and routing but not primary-source selection or source names. Canonicalization later rereads mutable is_primary and source.name; names participate in external OpenAPI dependency resolution. Promoting another already-versioned source or renaming a dependency can change executable parsing without changing the recorded configuration identity. A queued build can therefore use metadata different from its creation-time intent.

2. **Location & Evidence** — [`backend/app/domain/sources.py`][src-007] — source_configuration_fingerprint(); [`backend/app/domain/builds.py`][src-008] — BuildConfiguration; [`backend/app/models/build.py`][src-009] — BuildSourceVersion; [`backend/app/services/canonicalization/service.py`][src-010] — canonicalize() primary selection and external_documents keys; [`backend/app/services/builds/configuration_identity.py`][src-011] — current_sha256(); [`backend/app/services/sources.py`][src-004] — update() permits renaming and primary promotion without freezing existing build bindings.

3. **Criticality** — **High** — Reproducibility and stale-build protection omit inputs that determine the executable API.

4. **Recommended Solution** — Capture primary role and dependency-resolution aliases alongside each existing build/source binding. Include executable-affecting metadata in the canonical configuration fingerprint and use the frozen metadata during parsing rather than live source rows. Keep secret rotations outside executable identity. Update discovery, build creation, deployment checks, contracts, and migration handling together; require rebuilding historical records whose required identity cannot be established.

5. **Testing & Validation** — Create a queued build with two versioned executable sources, then switch the primary or rename an externally referenced source before worker execution. Assert the existing build remains bound to its original metadata, new discovery changes identity, and normal deployment rejects stale builds. Verify harmless metadata changes are classified consistently and historical artifacts are not rewritten.

6. **Resolution (2026-09-02)** — **Closed.** Migration `0021` freezes source ID/kind/name/origin/URL/creation time, primary role, dependency aliases, and routing beside each existing Build/source-version binding. The executable fingerprint includes those values and canonicalization consumes the frozen binding rather than mutable `ProjectSource` rows. Historical bindings are explicitly marked untrustworthy and fail new activation with an actionable rebuild requirement instead of receiving fabricated provenance. Unit and PostgreSQL tests prove queued-build immutability across rename/primary changes, fingerprint drift for new discovery, and fail-closed stale/historical deployment preflight. See [`docs/evidence/issues-002-foundation-closure.md`](docs/evidence/issues-002-foundation-closure.md).

---

### ISS-002-004 — Stop-first redeployment rejects its own scheduled stop as a conflicting deployment

1. **Description** — schedule_redeploy_active() schedules stops before requesting a replacement. Scheduling changes the old deployment to STOPPING. _request_in_session() then calls has_in_progress(), whose status set includes STOPPING, and rejects the replacement. Because both changes share one transaction, the stop and initiating mutation roll back. Credential rotation explicitly selects stop_old_first=True, so an active runtime encounters this self-conflict.

2. **Location & Evidence** — [`backend/app/services/deployment/service.py`][src-012] — schedule_redeploy_active(), _schedule_stop_in_session(), _request_in_session(); [`backend/app/repositories/deployments.py`][src-013] — has_in_progress(); [`backend/app/services/credentials.py`][src-014] — rotate().

3. **Criticality** — **High** — An intended security-maintenance operation cannot complete for an active deployment.

4. **Recommended Solution** — Make conflict detection transition-aware: distinguish stops owned by the replacement’s existing transition from unrelated in-progress work. Persist the stop and replacement command in their established order and retain the project serialization lock. Do not broadly ignore all STOPPING deployments. Apply the same correction when superseding an in-flight deployment and preserve rollback of genuinely invalid mutations.

5. **Testing & Validation** — With one RUNNING deployment, rotate an upstream credential and assert one committed ordered STOP→DEPLOY transition, successful eventual activation, and no self-conflict. Repeat with an in-flight deployment. Race an unrelated operator deployment and assert it cannot bypass mutual exclusion. Inject stop failure and assert the replacement does not execute prematurely.

6. **Resolution (2026-09-02)** — **Closed.** Deployment transitions now persist an explicit intent and transition ID. Replacement admission excludes only the STOPPING deployment IDs created by that same locked transaction; unrelated in-progress work remains conflicting. STOP and DEPLOY commands commit in sequence, and repository claim rules require the predecessor to become effective before the successor can execute. PostgreSQL tests prove ordered stop-first security refresh, unrelated-work exclusion, retry/replay ordering, and replacement suppression after stop failure. See [`docs/evidence/issues-002-foundation-closure.md`](docs/evidence/issues-002-foundation-closure.md).

---

### ISS-002-005 — Revoking the final static MCP token rolls back instead of removing access

1. **Description** — revoke_token() revokes a token and schedules a replacement runtime inside the same transaction. Deployment preflight materializes inbound authentication from active token verifiers, while InboundAuthSecrets rejects an empty static-token list. Revoking the last active token of a running static-bearer deployment therefore fails preflight and rolls back revocation; the existing runtime retains the token.

2. **Location & Evidence** — [`backend/app/services/mcp_access.py`][src-015] — revoke_token(); [`backend/app/services/deployment/service.py`][src-012] — schedule_redeploy_active(), _request_in_session(); [`backend/app/services/deployment/preflight.py`][src-016] — validate() inbound-auth materialization; [`packages/contracts/src/mcp_contracts/runtime_secrets.py`][src-017] — InboundAuthSecrets.mode_configuration_is_complete().

3. **Criticality** — **High** — The operator cannot complete the intended removal of the final accepted access credential.

4. **Recommended Solution** — Separate revocation effectiveness from replacement deployability within the existing lifecycle service. When no valid inbound verifier remains, commit revocation together with durable STOP commands for affected live/in-flight runtimes rather than constructing an invalid replacement. Preserve fail-closed authentication and accurate pending/failed/effective status until runtime shutdown is observed. Never restore the revoked token merely to satisfy deployment validation.

5. **Testing & Validation** — Revoke the only token on a running project and assert the database revocation commits, STOP is durable, no invalid replacement is created, and the old token stops working when the command becomes effective. Repeat with multiple tokens, expired tokens, duplicate requests, queue outage, worker restart, and stop failure; never report effectiveness before observation.

6. **Resolution (2026-09-02)** — **Closed.** Revocation now evaluates the materialized valid-verifier set under the project lock. Removing the final verifier commits the revocation and one durable STOP command without constructing an invalid replacement; duplicate revocation returns the existing lifecycle effect and cannot create another transition. Multiple-token changes retain the exact active build through the security-refresh path. PostgreSQL and unit regressions cover final/subset/expired/duplicate revocation, durable outbox behavior, queue restart, and truthful pending/effective/failed state. See [`docs/evidence/issues-002-foundation-closure.md`](docs/evidence/issues-002-foundation-closure.md).

---

### ISS-002-006 — Authentication-only runtime maintenance is blocked by unrelated source drift

1. **Description** — Authentication and credential changes redeploy the active build through _request_in_session() with require_current_configuration=True. Uploading a newer source or changing routing makes the active build stale even though it remains the deployed artifact. Subsequent token creation, rotation, or revocation can then fail BUILD_INPUTS_STALE and roll back, coupling access maintenance to a rebuild of unrelated executable inputs.

2. **Location & Evidence** — [`backend/app/services/deployment/service.py`][src-012] — schedule_redeploy_active() and default require_current_configuration in _request_in_session(); [`backend/app/services/deployment/preflight.py`][src-016] — validate() configuration comparison; [`backend/app/services/mcp_access.py`][src-015] — create_token(), rotate_token(), revoke_token(); [`backend/app/services/credentials.py`][src-014] — rotate().

3. **Criticality** — **High** — Security maintenance can be unavailable while an operator is preparing the next source revision.

4. **Recommended Solution** — Give existing lifecycle commands an explicit, narrowly scoped authentication-refresh intent. For that intent, reuse the exact active immutable build and validate its artifact, compatibility, ownership, and current secret material without requiring unrelated pending source/routing inputs to match. Keep current-configuration enforcement for normal new deployments. Use the existing stop behavior whenever the refreshed authentication cannot safely support execution.

5. **Testing & Validation** — Deploy build A, upload source B without deploying it, then create/rotate/revoke access tokens and rotate a used credential. Assert maintenance applies to A or safely stops it, never deploys B implicitly, and never rolls back solely due to source drift. Assert ordinary deployment of stale A still fails and cross-project artifacts remain rejected.

6. **Resolution (2026-09-02)** — **Closed.** Migration `0023` adds `normal`, `security_refresh`, and `rollback` deployment intent. Security refresh is bound to the exact active immutable build and bypasses only current-source identity comparison; artifact integrity, project ownership, runtime compatibility, and current secret material remain mandatory. If the active build cannot be safely rematerialized, the security mutation commits with a durable STOP instead of rolling back. Tests prove source B is never activated implicitly, normal stale-A activation still fails, and untrusted/cross-project inputs remain fail-closed. See [`docs/evidence/issues-002-foundation-closure.md`](docs/evidence/issues-002-foundation-closure.md).

---

### ISS-002-007 — Build cancellation can lose its worker before cancellation is acknowledged

1. **Description** — Admission renewal rejects builds with cancellation_requested_at set, and the dispatcher releases their lease and excludes them from new claims. The heartbeat treats renewal rejection as lost admission, cancels the owner task, and the job exits on CancelledError. BuildPipeline acknowledges its custom cancellation exception or InvalidStateError, not this task cancellation. If the heartbeat wins during a long stage, or the worker dies after cancellation, the build can remain nonterminal indefinitely and block the project’s next build.

2. **Location & Evidence** — [`backend/app/repositories/build_admission.py`][src-018] — begin_or_renew(), claim_available(); [`backend/app/jobs/build.py`][src-019] — _heartbeat_admission(), _run() CancelledError branch; [`backend/app/services/builds/pipeline.py`][src-020] — run() cancellation handlers; [`backend/app/services/builds/service.py`][src-021] — cancel(); [`backend/app/models/build.py`][src-009] — uq_builds_one_active_per_project.

3. **Criticality** — **High** — Cancellation can strand durable work and prevent further builds for the project.

4. **Recommended Solution** — Distinguish requested cancellation from superseded ownership. Route cancellation through the existing idempotent acknowledgement/cleanup transaction before releasing ownership where possible. Extend the existing dispatcher’s recovery logic to finalize cancellation requests whose worker/lease is gone, without executing more pipeline stages. Preserve cleanup reference protection and prevent stale workers from publishing results after acknowledgement.

5. **Testing & Validation** — Pause a running stage beyond the heartbeat interval, request cancellation, and force renewal rejection before the next pipeline checkpoint. Assert eventual CANCELLED, acknowledgement timestamp, released admission, captured cleanup, and ability to create the next build. Repeat with abrupt worker termination, Redis outage, duplicate cancellation, and a late stage result.

6. **Resolution (2026-09-02)** — **Closed.** Requested cancellation no longer invalidates a live owner’s admission lease. The owner acknowledges through one idempotent cancellation/cleanup transaction at pipeline boundaries; if that owner dies or expires, dispatcher recovery claims the cancellation specifically and finalizes it without running another stage. Queue failure and duplicate requests retain durable state, release only the exact owned admission, and permit the project’s next build. Unit and PostgreSQL tests cover long-stage cancellation, dead-owner recovery, duplicate acknowledgement, cleanup capture, and replacement-build admission. See [`docs/evidence/issues-002-foundation-closure.md`](docs/evidence/issues-002-foundation-closure.md).

---

### ISS-002-008 — Build lease loss is not fenced at pipeline state and result writes

1. **Description** — The build heartbeat logs renewal exceptions and continues; it does not stop work when the last confirmed lease expires. The dispatcher can reclaim expired work with a new token. Pipeline transition/result repository updates check build ID and stage but not the admission token. The previous worker can therefore remain active and race a replacement worker, especially during provider calls or a temporary database outage.

2. **Location & Evidence** — [`backend/app/jobs/build.py`][src-019] — _heartbeat_admission() exception branch; [`backend/app/repositories/build_admission.py`][src-018] — claim_available() expired-lease reclamation; [`backend/app/repositories/builds.py`][src-022] — transition(), _stage_update(), fail(); [`backend/app/services/builds/pipeline.py`][src-020] — run() and stage persistence.

3. **Criticality** — **High** — Reclaimed jobs can produce duplicate paid work and accept results from an obsolete execution owner.

4. **Recommended Solution** — Carry the existing admission token through pipeline execution and condition every ownership-sensitive transition/result publication on the current token. Track the last confirmed lease deadline and stop issuing new external work once ownership cannot be established. Use database time consistently for claims, distinguish cancellation recovery, and discard late results from old owners rather than overwriting current build evidence.

5. **Testing & Validation** — Pause worker A in a provider request, make heartbeat renewal fail through lease expiry, and let worker B claim the build. Resume A and assert its result/state writes affect zero rows and cannot fail or complete B’s build. Verify normal renewal, delayed responses, cancellation, and connection recovery do not duplicate accepted artifacts or usage records.

6. **Resolution (2026-09-02)** — **Closed.** The admission token is now carried through the canonical pipeline and every ownership-sensitive Build, stage, validation, AI-run, artifact, usage, and index-generation publication verifies the live database lease and exact token. The heartbeat uses a monotonic deadline derived from the last database-confirmed lease and cancels new work after ownership uncertainty reaches expiry. Migration `0025` records the accepted execution token on index generations; physical Milvus row IDs are attempt-scoped while canonical chunk IDs remain stable, so stale cleanup cannot delete a replacement’s rows. PostgreSQL and vector tests resume a stale worker after reclaim and reject every late writer/result. See [`docs/evidence/issues-002-foundation-closure.md`](docs/evidence/issues-002-foundation-closure.md).

---

### ISS-002-009 — Runtime lifecycle command leases have no execution-owner fencing or renewal

1. **Description** — Commands are leased and may be redispatched after expiry, but the queue passes only command_id to execution. RuntimeCommandExecutor runs the deployment/stop without renewing ownership; mark_effective() and mark_failed() are not conditional on an execution token or claimed attempt. A slow or stalled prior worker can race a new attempt and alter its status. A lease alone does not establish safe ownership across external Docker effects.

2. **Location & Evidence** — [`backend/app/repositories/runtime_commands.py`][src-023] — claim_due_for_dispatch(), claim_for_execution(), mark_effective(), mark_failed(); [`backend/app/services/deployment/command_executor.py`][src-024] — run(), _verify_and_mark_effective(); [`backend/app/clients/queue.py`][src-025] — enqueue_runtime_command().

3. **Criticality** — **High** — Concurrent lifecycle attempts can compromise ordered recovery and reported runtime effectiveness.

4. **Recommended Solution** — Add ownership fencing to the existing command record/claim contract and pass the claimed attempt or token into execution and terminal updates. Renew ownership during long operations and verify it before destructive Docker actions and activation writes. Reconcile already-observed effects idempotently after crashes. Ensure predecessors remain effective before successors execute, including after redispatch; do not add a second command queue or execution path.

5. **Testing & Validation** — Run a command longer than its lease, redispatch it, and resume the stale attempt. Assert stale terminal writes are rejected and only the current owner may activate or stop the target. Cover duplicate queue delivery, reordered STOP/DEPLOY commands, crash after Docker success, and failure during lease renewal.

6. **Resolution (2026-09-02)** — **Closed.** Migration `0022` adds the execution token to the durable command claim, queue payload, lease renewal, ownership checkpoints, and exact-token terminal updates. Claims and renewal use PostgreSQL time; the executor stops at its last confirmed monotonic deadline and holds a PostgreSQL session advisory project lock around Docker effects. Predecessor effectiveness is rechecked, deployment state writes are fenced, and STOP verifies then targets the exact recorded container ID rather than a reusable name. Unit and PostgreSQL concurrency tests cover duplicate/reordered delivery, reclaim, stale finalization, database-heartbeat outage, project serialization, exact-container stop, and crash/retry reconciliation. See [`docs/evidence/issues-002-foundation-closure.md`](docs/evidence/issues-002-foundation-closure.md).

---

### ISS-002-010 — Production browser API proxy forwards a host rejected by the API

1. **Description** — The frontend serves same-origin /api/ requests and proxies them with Host $host, which is the UI domain. Production TrustedHostMiddleware permits api_domain plus loopback hosts, not the separate UI domain. The production Compose override explicitly supports distinct UI_DOMAIN and API_DOMAIN. Under that configuration, browser API requests can receive an invalid-host response while direct requests to the API domain work.

2. **Location & Evidence** — [`infra/docker/nginx.conf`][src-026] — location /api/, proxy_set_header Host $host; [`backend/app/main.py`][src-027] — create_app() production TrustedHostMiddleware; [`infra/compose.production.yaml`][src-028] — frontend UI_DOMAIN and api API_DOMAIN routing.

3. **Criticality** — **High** — The documented production domain topology can break the entire browser control plane.

4. **Recommended Solution** — Derive the exact UI hostname from the validated frontend_origin and include it alongside api_domain in the existing production TrustedHostMiddleware allowlist, matching the same-origin Nginx proxy contract. Preserve strict host validation, CSRF origin checks, and trustworthy forwarded-protocol handling rather than allowing wildcard hosts. Validate and document both configured public domains together.

5. **Testing & Validation** — Deploy with distinct UI and API domains behind TLS. Exercise login, refresh, authenticated reads, mutations, and event streams through the UI origin. Assert success, correct secure-cookie behavior, and rejection of an unrelated Host header. Verify direct API-domain requests and the existing loopback health check still work.

---

### ISS-002-011 — Exported production Compose example omits mandatory runtime authentication settings

1. **Description** — The export generator emits MCP_ENVIRONMENT=production and the manifest digest, but does not supply MCP_AUTH_OVERLAY_SHA256 or MCP_ALLOWED_ORIGINS. RuntimeSettings requires an authentication-overlay digest in production and requires the public origin in allowed_origins. Following the generated example with the variables it requests therefore still fails runtime configuration validation.

2. **Location & Evidence** — [`backend/app/services/artifacts.py`][src-029] — _compose_example(), _readme(), package(); [`mcp_runtime/app/core/config.py`][src-030] — RuntimeSettings.production_security_invariants(); [`mcp_runtime/app/main.py`][src-031] — secret-bundle loading with auth_overlay_sha256.

3. **Criticality** — **High** — A generated deployment artifact cannot start under the security rules of its own runtime.

4. **Recommended Solution** — Update the existing export template and README together to declare every required production input, including the digest computed from the separately supplied secret-bundle bytes and an exact allowed public origin. Keep secret material outside the export. Make example host, origin, input-path, size, and runtime-compatibility settings consistent with the runtime contract; never weaken production validation to accommodate the incomplete template.

5. **Testing & Validation** — Generate an export, provide a temporary valid secret bundle and the documented variables, render its Compose configuration, and start the pinned runtime. Assert readiness and authenticated MCP access. Missing or altered secret hashes and incorrect origins must fail. Assert exported files contain neither credentials nor token plaintext.

---

### ISS-002-012 — OpenRouter catalog requests exclude the embedding models required by build configuration

1. **Description** — OpenRouterClient.models() calls /models without output_modalities. The current official API defaults that endpoint to text-output models. SettingsService validates embedding_model against this same catalog, while BuildService requires an embedding model. This leaves the normal catalog-driven configuration path unable to select embedding-only models even though the client can send embedding requests.

2. **Location & Evidence** — [`backend/app/clients/ai.py`][src-032] — models(); [`backend/app/services/settings.py`][src-033] — _validate_model_changes(), model_catalog(), _supports_embeddings(); [`backend/app/services/builds/service.py`][src-021] — create() mandatory model checks. Provider contract: [OpenRouter Models API](https://openrouter.ai/docs/api/api-reference/models/get-models), output_modalities default, verified on 2026-09-01.

3. **Criticality** — **High** — The configured provider discovery path can prevent completing model setup and creating builds.

4. **Recommended Solution** — Extend the existing client request interface to send /models with output_modalities=all, then preserve modality metadata through the existing provider and settings DTOs. Filter analysis/validation and embedding selections by their actual capabilities. Keep one normalized catalog and existing error handling; update request metrics and contract fixtures for query parameters rather than hardcoding model IDs.

5. **Testing & Validation** — Use a provider-contract fixture where default /models returns text models only and the all-modalities request also returns an embedding-only model. Assert the correct query, visible embedding selection, successful settings validation, and successful build creation. Reject a text-only model for embeddings and preserve provider-error behavior.

---

### ISS-002-013 — Canonicalization loads all bound source payloads concurrently, including unused documentation bytes

1. **Description** — canonicalize() gathers storage reads for every binding and retains all returned byte buffers in a dictionary. It then parses executable sources, while documentation contributes only metadata references. Thus a project with multiple large documentation uploads can allocate their combined raw size during source discovery/build canonicalization even though those bytes are unnecessary there. Per-file limits do not bound this aggregate allocation.

2. **Location & Evidence** — [`backend/app/services/canonicalization/service.py`][src-010] — canonicalize() payloads asyncio.gather(), content dictionary, documentation_refs; [`backend/app/services/builds/pipeline.py`][src-020] — _canonicalize(); [`backend/app/services/sources.py`][src-004] — configuration-discovery integration.

3. **Criticality** — **High** — Normal accepted inputs can exhaust API or worker memory and interrupt unrelated work.

4. **Recommended Solution** — Read only the primary executable source and the immutable executable dependencies required for reference resolution. Construct documentation references from existing metadata without loading their bodies. Bound concurrent reads using the existing concurrency utility and enforce an aggregate executable-input budget before allocation. Keep documentation parsing in its existing indexing boundary and produce an explicit limit error instead of process exhaustion.

5. **Testing & Validation** — Attach several large documentation objects plus a small executable specification. Assert canonicalization never reads documentation bodies and memory does not grow with their byte total. Test many executable dependencies, an aggregate-limit breach, missing objects, cancellation, and unchanged canonical output for valid projects.

---

### ISS-002-014 — Long-running Compose services lack restart policies for production recovery

1. **Description** — Milvus explicitly uses restart: unless-stopped, but the API, workers, runtime validator, frontend, edge proxy, PostgreSQL, Redis, etcd, and MinIO do not declare corresponding restart behavior. The production override does not add it. Docker health checks report status but do not provide the missing process/daemon-restart policy, leaving major services stopped after a crash or host restart.

2. **Location & Evidence** — [`infra/compose.yaml`][src-034] — long-running service definitions; Milvus restart policy contrasted with other services; [`infra/compose.production.yaml`][src-028] — service overrides.

3. **Criticality** — **High** — A routine infrastructure restart can leave the control plane, persistence, or execution workers unavailable until manual intervention.

4. **Recommended Solution** — Set the intended production restart policy on existing long-running services and document recovery ordering and failure visibility. Keep migration and runtime-init one-shot services non-restarting. Ensure service initialization tolerates dependencies returning later and that health failure is not confused with automatic repair. Preserve the existing topology and do not add deployment testing steps.

5. **Testing & Validation** — Render the merged production Compose configuration and assert restart policies on every long-running service and restart: no on one-shot jobs. In an isolated operational test, kill an API/worker process and restart the Docker daemon; assert recovery, preserved volumes, and resumed durable commands without duplicate effects.

---

### ISS-002-015 — Project/deployment row locks are acquired in opposite orders

1. **Description** — Project stop/disable paths lock the project and then update deployment rows. Activation and recovery repository paths lock a deployment and then the project. Concurrent activation and project shutdown can therefore form a project→deployment versus deployment→project lock cycle, causing deadlock aborts in lifecycle transactions.

2. **Location & Evidence** — [`backend/app/services/deployment/service.py`][src-012] — schedule_stop_project(), _schedule_stop_in_session(); [`backend/app/services/projects.py`][src-035] — update() disable branch; [`backend/app/repositories/deployments.py`][src-013] — begin_activation(), complete_activation(), restore_previous_after_failed_activation().

3. **Criticality** — **Medium** — Conflicting lifecycle requests can fail transiently and complicate security-related shutdown or activation recovery.

4. **Recommended Solution** — Establish one lock order for the existing lifecycle operations: project first, then affected deployments in deterministic identifier order, then command/subject rows as needed. Obtain the immutable project identifier before acquiring deployment mutation locks and revalidate under the project lock. Preserve transaction atomicity and explicit state predicates; retries are secondary protection, not the root-cause fix.

5. **Testing & Validation** — Use two real PostgreSQL transactions with barriers to overlap activation with disable/stop and failed-activation recovery with replacement. Assert no deadlock, a serializable intended outcome, valid active pointers, and no competing RUNNING deployment. Verify repeated stop remains idempotent.

---

### ISS-002-016 — Configured upload capacity can exceed the API multipart spool filesystem

1. **Description** — SystemSettingsUpdate permits max_upload_bytes up to 500,000,000, and Nginx accepts bodies up to 500m. The API /tmp spool is only 256m, and the Compose comment confirms multipart spooling occurs before the bounded storage layer reads the upload. A permitted larger upload, or multiple concurrent default-sized uploads, can exhaust that filesystem before application-level validation.

2. **Location & Evidence** — [`backend/app/schemas/setting.py`][src-036] — SystemSettingsUpdate.max_upload_bytes; [`infra/compose.yaml`][src-034] — api.tmpfs and multipart-spooling comment; [`infra/docker/nginx.conf`][src-026] — client_max_body_size; [`backend/app/api/sources.py`][src-037] — UploadFile routes.

3. **Criticality** — **Medium** — Accepted configuration values can produce upload failures and shared temporary-storage exhaustion.

4. **Recommended Solution** — Reconcile upload limits, request-envelope overhead, concurrent upload admission, and spool capacity in the existing API/proxy configuration. Enforce total streamed request size before unbounded multipart spooling and bound concurrent spool consumption. Keep the storage-level limit as defense in depth, and return a structured 413 or explicit capacity response rather than ENOSPC/500.

5. **Testing & Validation** — Test the documented default and maximum supported upload sizes, one byte over each limit, multipart overhead, and concurrent boundary-sized uploads. Assert bounded /tmp use, deterministic rejection, partial-file cleanup after disconnect, and no impact on small unrelated requests.

---

### ISS-002-017 — API startup depends on Milvus despite the control-plane outage-isolation contract

1. **Description** — The readiness implementation deliberately treats Milvus and OpenRouter as optional builder dependencies so an outage does not disable existing-project control-plane access. Compose nevertheless requires Milvus to be healthy before starting the API, and the frontend depends on the API. A fresh start or recovery during a Milvus outage therefore blocks the control plane before its degraded-mode readiness logic can run.

2. **Location & Evidence** — [`backend/app/api/health.py`][src-038] — ready() optional builder-dependency comment and ready_value; [`infra/compose.yaml`][src-034] — api.depends_on.milvus; frontend.depends_on.api.

3. **Criticality** — **Medium** — The intended dependency isolation does not hold during startup and recovery.

4. **Recommended Solution** — Remove the builder-only startup dependency from the API’s essential startup requirements while retaining it where build execution genuinely needs it. Initialize optional clients without preventing control-plane startup and expose their degraded status through the existing health contract. Keep build operations explicit about unavailable builder dependencies instead of changing unrelated control-plane access.

5. **Testing & Validation** — Start with PostgreSQL/Redis healthy and Milvus unavailable. Assert the API/frontend start, authentication and existing-project reads work, readiness identifies the degraded builder dependency, and builds fail or wait with an actionable state. Restore Milvus and assert recovery without recreating the control plane.

---

### ISS-002-018 — Custom runtime UID/GID settings conflict with the deployment worker’s fixed identity

1. **Description** — runtime-init gives the mount root ownership to configurable RUNTIME_UID/RUNTIME_GID and mode 0700. The backend image runs the deployment worker as fixed 10001:10001 with dropped capabilities. Changing the runtime UID from its default can make the root inaccessible to the worker; RuntimeFilesClient also attempts ownership changes that the unprivileged worker cannot perform for arbitrary IDs.

2. **Location & Evidence** — [`infra/compose.yaml`][src-034] — runtime-init ownership and deployment-worker identity/capabilities; [`infra/docker/backend.Dockerfile`][src-039] — USER 10001:10001; [`backend/app/clients/runtime_files.py`][src-040] — _ensure_root(), _set_owner(), _materialize(); [`.env.example`][src-041] — RUNTIME_UID and RUNTIME_GID.

3. **Criticality** — **Medium** — Exposed configuration knobs can make all runtime deployment fail with permission errors.

4. **Recommended Solution** — Define and enforce a coherent ownership contract for the existing worker and runtime. Support configured IDs through image/user configuration and narrowly scoped initialization, or reject unsupported combinations during configuration validation. Keep the worker non-root and secret files private; do not solve the mismatch with world-readable directories or broad permanent capabilities.

5. **Testing & Validation** — Test default and non-default UID/GID combinations on Linux bind mounts. Assert worker materialization, runtime reads, secure modes, cleanup, and restart recovery. Unsupported combinations must fail configuration checks with a precise error before attempting deployment.

---

### ISS-002-019 — Operation-exclusion input normalization raises unhandled exceptions for non-string JSON values

1. **Description** — OperationExclusionCreate.normalize_text() is a mode="before" validator and calls value.strip() without checking the raw input type. Inputs such as null, integers, arrays, or objects raise AttributeError rather than the intended validation error, converting malformed input into a server error instead of a structured 422 response.

2. **Location & Evidence** — [`backend/app/schemas/build.py`][src-042] — OperationExclusionCreate.normalize_text(); [`backend/app/api/builds.py`][src-043] — create_operation_exclusion(); [`backend/app/main.py`][src-027] — domain-error handler. Validator semantics: [Pydantic before validators](https://docs.pydantic.dev/latest/concepts/validators/#field-validators).

3. **Criticality** — **Medium** — Malformed authenticated requests violate the API error contract and unnecessarily produce server failures.

4. **Recommended Solution** — Accept raw object/Any in the before validator, explicitly validate that it is a string, and raise a supported validation error for other types before normalization. Retain post-normalization length constraints and the service’s defensive validation. Regenerate the affected contract only if its public schema changes.

5. **Testing & Validation** — Submit each field as null, number, boolean, list, and object; assert 422 with field location and no database mutation. Verify whitespace-only text, normalized minimum-length reasons, maximum-length boundaries, and valid values. Assert no AttributeError escapes the request boundary.

---

### ISS-002-020 — Operational settings accept explicit null for fields that the persisted/read contract requires

1. **Description** — SystemSettingsUpdate makes operational fields optional and nullable, including build_concurrency, builders_can_deploy, and max_upload_bytes. update_operational() merges explicitly supplied null values into the current settings and validates with SystemSettingsRead, which requires non-null values for these fields. That internal Pydantic failure is not translated to the domain validation envelope, so schema-accepted requests can fail as 500 errors.

2. **Location & Evidence** — [`backend/app/schemas/setting.py`][src-036] — SystemSettingsUpdate versus SystemSettingsRead; [`backend/app/services/settings.py`][src-033] — update_operational() merged model_validate(); [`backend/app/main.py`][src-027] — handle_domain_error().

3. **Criticality** — **Medium** — The request and persistence contracts disagree and make routine settings updates fail unpredictably.

4. **Recommended Solution** — Distinguish omission from explicit null. Permit null only for settings with a defined reset/disabled meaning, such as nullable retention fields. Reject null for required operational values at request validation and validate the fully merged object before persistence, translating expected validation failures into the existing 422 envelope. Keep existing settings unchanged on failure.

5. **Testing & Validation** — Send explicit null for every writable setting and assert the documented result per field. Required fields must return 422, retention resets must round-trip correctly, omitted fields must remain unchanged, and concurrent partial updates must preserve validated values and audit only committed changes.

---

### ISS-002-021 — Cleared model settings silently reappear from environment defaults

1. **Description** — ModelSettingsUpdate accepts null or blank model IDs, and update_models() can persist them. _models_from_records() uses _optional_string(), which falls back to environment values for both absent and explicitly cleared values. With configured environment defaults, a successful clear response can therefore disagree with the next GET and builds continue using a model the operator attempted to unset.

2. **Location & Evidence** — [`backend/app/schemas/setting.py`][src-036] — ModelSettingsUpdate.normalize_model(); [`backend/app/services/settings.py`][src-033] — update_models(), _models_from_records(), _optional_string().

3. **Criticality** — **Medium** — Effective configuration and operator-visible persisted intent can diverge.

4. **Recommended Solution** — Give missing and explicit-null stored values different meanings. Apply environment defaults only when the stored key is absent, unless the public operation explicitly requests a reset-to-environment action. Make PUT responses, subsequent GETs, and build snapshots derive from the same effective configuration function and document the chosen clear/reset behavior.

5. **Testing & Validation** — Set environment defaults, persist custom models, then clear each model with null and blank text. Assert response/GET/build behavior agrees and no silently resurrected value appears. Verify an installation with no stored key still receives its environment default and partial updates preserve other settings.

---

### ISS-002-022 — Credential creation accepts values rejected by the runtime credential contract

1. **Description** — Control-plane validate_credential_secret() accepts Basic usernames containing a colon and static header values containing CR/LF/NUL; it also does not reject case-insensitive duplicate static header names. UpstreamCredential rejects those values when runtime secret material is constructed. The API can therefore save an unusable credential and defer failure until deployment. Scalar bearer/header secrets also need transport-safe validation at their existing boundary.

2. **Location & Evidence** — [`backend/app/domain/credentials.py`][src-044] — validate_credential_secret(); [`backend/app/schemas/credential.py`][src-045] — CredentialCreate.validate_secret_shape(), CredentialRotate; [`packages/contracts/src/mcp_contracts/runtime_secrets.py`][src-017] — UpstreamCredential.validate_exact_secret_shape(); [`backend/app/services/deployment/secret_materializer.py`][src-046] — runtime credential construction.

3. **Criticality** — **Medium** — Invalid security configuration is accepted early and causes later runtime deployment or request failures.

4. **Recommended Solution** — Reuse compatible infrastructure-free validation rules from the existing shared contract, preserving control-plane field naming through the existing mapping. Reject invalid Basic usernames, unsafe header values, and case-insensitive duplicate names before persistence on creation and rotation. Apply field-specific encoding rules rather than forbidding valid characters in unrelated password/client-secret fields.

5. **Testing & Validation** — Test Basic usernames with colons, static header names differing only by case, CR/LF/NUL values, empty values, valid Unicode passwords, and valid query API keys. Assert invalid inputs return 422 without persistence or lifecycle effects, and every accepted credential can materialize and execute with the runtime contract.

---

### ISS-002-023 — Operation exclusions are not applied consistently to build preflight

1. **Description** — BuildService.create() loads persistent exclusions but checks discovery.routing_complete and credential_mapping_readiness() across the full discovered operation set. The compiler’s map_credentials() explicitly skips excluded operations. A deliberately excluded operation with unresolved routing or authentication can still prevent creating the build that should omit it.

2. **Location & Evidence** — [`backend/app/services/builds/service.py`][src-021] — create() routing/credential checks and excluded_operations snapshot; [`backend/app/services/builds/readiness.py`][src-047] — credential_mapping_readiness(); [`backend/app/services/builds/credential_mapping.py`][src-048] — map_credentials() excluded_operation_keys.

3. **Criticality** — **Medium** — Exclusion behavior differs between preflight and compilation, blocking otherwise valid included operations.

4. **Recommended Solution** — Derive the included operation set once from the frozen source identity and exclusion snapshot. Use it consistently in per-operation routing readiness, credential readiness, compilation, and coverage validation. Continue rejecting structural corruption that prevents trustworthy source interpretation, and do not silently classify unsupported included operations as excluded.

5. **Testing & Validation** — Create a source with one valid operation and one persistently excluded operation whose routing/authentication is unresolved. Assert the included operation builds with accurate coverage. Remove the exclusion and assert an actionable preflight failure. Verify exclusions remain immutable for already-created builds and unrelated invalid source structure is still rejected.

---

### ISS-002-024 — Credential readiness and compilation use divergent selection rules

1. **Description** — Readiness checks OAuth advertised/default scopes and token-auth method while filtering candidates, then can try another security alternative. Compiler mapping filters a different set of properties and only validates scopes in _selection() after choosing a candidate; an exception there aborts mapping rather than trying the next usable alternative. The two implementations can disagree about whether a source’s authentication is executable.

2. **Location & Evidence** — [`backend/app/services/builds/readiness.py`][src-047] — _compatible_values(), credential_mapping_readiness(); [`backend/app/services/builds/credential_mapping.py`][src-048] — _compatible(), _selection(), map_credentials().

3. **Criticality** — **Medium** — A configuration reported ready can fail later in compilation, increasing failed builds and diagnostic ambiguity.

4. **Recommended Solution** — Extract one pure selection algorithm inside the existing build-service boundary and use adapters for discovery records and canonical records. Make compatibility, explicit bindings, scope validation, ambiguity, and alternative ordering identical. Return structured rejection reasons and a selection plan that compilation consumes, rather than maintaining separate interpretations.

5. **Testing & Validation** — Run the same cases through readiness and compilation: source scope changes, invalid credential default scopes, multiple candidates, explicit scheme bindings, anonymous alternatives, and an unusable first alternative followed by a valid one. Assert identical eligibility and selected credentials, with consistent failures when no alternative is valid.

---

### ISS-002-025 — Canonical path validation rejects embedded and multiple placeholders in one segment

1. **Description** — CanonicalOperation identifies path parameters by splitting on slashes and accepting only segments that start with "{" and end with "}". Valid templates such as /files/{id}.json are missed, while /coordinates/{lat},{lon} is interpreted as one parameter. ApiInventory’s earlier validator uses a brace-matching expression, so a document can pass inventory validation and fail canonical conversion.

2. **Location & Evidence** — [`packages/contracts/src/mcp_contracts/canonical.py`][src-049] — CanonicalOperation.validate_path_parameters(); [`packages/contracts/src/mcp_contracts/inventory.py`][src-050] — _PATH_PARAMETER and InventoryOperation.validate_path_parameters().

3. **Criticality** — **Medium** — Valid source APIs are rejected inconsistently across shared contract layers.

4. **Recommended Solution** — Use one shared path-template parser that identifies every balanced placeholder regardless of segment position and rejects malformed braces explicitly. Reconcile inventory, canonical, compiler, and runtime substitution behavior using that parser without weakening traversal/destination safety checks. Preserve case-sensitive parameter names and correct percent encoding.

5. **Testing & Validation** — Test /files/{id}.json, /coordinates/{lat},{lon}, multiple segments, missing/extra declarations, unmatched braces, and encoded delimiters. Assert accepted templates survive source→canonical→manifest→runtime with exact parameter substitution and rejected templates fail consistently at the earliest appropriate boundary.

---

### ISS-002-026 — API Inventory schema materialization rewrites literal data as executable schema references

1. **Description** — _materialize_schema() recursively visits every dictionary/list, treats any $ref key as a schema reference, and removes $defs wherever encountered. It does not distinguish schema-valued keywords from instance-valued annotations such as default, examples, const, or enum. Valid literal payload examples containing a $ref or $defs property can therefore be altered or cause reference-resolution failure.

2. **Location & Evidence** — [`backend/app/parsers/api_inventory/parser.py`][src-051] — _materialize_schema() nested visit() and key filtering.

3. **Criticality** — **Medium** — The parser can reject valid inventories or change their literal data/validation meaning.

4. **Recommended Solution** — Make traversal JSON-Schema-keyword aware. Resolve references only in schema positions, preserve instance-valued annotations verbatim, and handle definitions with their correct resource scope. Retain the existing immutable-source restriction on external executable references. Keep the normalized schema’s semantics and examples traceable to the original source.

5. **Testing & Validation** — Use schemas whose default, examples, const, and enum contain literal objects with $ref/$defs properties; assert byte-equivalent logical data after materialization. In the same fixtures include real nested schema references and assert they still resolve. Validate representative instances against original and materialized schemas and compare outcomes.

---

### ISS-002-027 — API Inventory JSON Pointer traversal cannot resolve array elements

1. **Description** — The inventory _pointer() resolver traverses dictionaries only. Valid local pointers into schema arrays, for example #/allOf/0 or #/prefixItems/1, fail even when the target exists. The same resolver is used during materialization, so schema compositions that refer to array-contained subschemas cannot be consumed.

2. **Location & Evidence** — [`backend/app/parsers/api_inventory/parser.py`][src-051] — _pointer() and _materialize_schema() target lookup.

3. **Criticality** — **Medium** — Valid local schema-reference patterns fail at the parser boundary.

4. **Recommended Solution** — Implement complete local JSON Pointer traversal for dictionary keys and valid array indices, including fragment decoding and ~0/~1 handling, in the existing resolver. Reject malformed indices, missing targets, and invalid schema targets deterministically. Preserve cycle handling and immutable external-reference restrictions; do not fall back to network resolution.

5. **Testing & Validation** — Resolve pointers into allOf, anyOf, and prefixItems arrays, escaped property names, and percent-encoded fragments. Test negative/non-numeric/out-of-range indices and recursive references. Assert deterministic canonical output and clear source-attributed errors for invalid pointers.

---

### ISS-002-028 — Response validation can bypass an exact status definition through a less-specific fallback

1. **Description** — validate_upstream_response() selects media inside a loop over exact status, status class, and default. When an exact status exists but its media type does not match, the loop continues to a range/default definition. A response that violates its explicit status contract can therefore be accepted under a less-specific response definition.

2. **Location & Evidence** — [`mcp_runtime/app/executor/response_contract.py`][src-052] — validate_upstream_response(), _select_media(). Normative precedence: [OpenAPI 3.1.1 Responses Object](https://spec.openapis.org/oas/v3.1.1.html#responses-object).

3. **Criticality** — **Medium** — Successful tool responses can be reported as valid despite violating the compiled operation contract.

4. **Recommended Solution** — Resolve the applicable response status definition first: exact status if declared, otherwise matching range, otherwise default. Select and validate media only within that chosen definition; a media mismatch must not trigger status fallback. Preserve existing no-body handling and schema validation, and keep sanitized error-response behavior explicit.

5. **Testing & Validation** — Declare 200/application-json and default/text-plain, then return 200/text-plain; assert contract rejection. Cover exact-over-range precedence, valid range/default use for undeclared statuses, media wildcards, empty 204 bodies, and valid JSON null without confusing it with absence of an HTTP body.

---

### ISS-002-029 — OIDC discovery changes the configured issuer identifier by stripping its trailing slash

1. **Description** — OidcJwksClient normalizes issuer_url with rstrip("/") and later compares the discovery document’s issuer to that changed value. An issuer whose registered identifier ends in a slash is not equivalent to the stripped identifier. Such a valid provider can fail discovery even when configured correctly; issuer identity and discovery-URL construction require different treatment.

2. **Location & Evidence** — [`mcp_runtime/app/clients/oidc_client.py`][src-053] — OidcJwksClient.__init__(), _discover_jwks_url(); [`packages/contracts/src/mcp_contracts/runtime_secrets.py`][src-017] — InboundAuthSecrets.issuer_url. Identity requirement: [OpenID Connect Discovery 1.0, provider-configuration validation](https://openid.net/specs/openid-connect-discovery-1_0.html#ProviderConfigurationValidation).

3. **Criticality** — **Medium** — OIDC integration can fail for a valid configured issuer, preventing authenticated runtime access.

4. **Recommended Solution** — Preserve the exact configured issuer string for discovery and token-issuer comparison. Derive the well-known discovery URL separately using the specification’s URL-construction rule. Reconcile any issuer normalization at materialization and authentication boundaries; reject genuine issuer mismatches rather than normalizing them into equality.

5. **Testing & Validation** — Test issuers with and without a trailing slash, including a path-based issuer. Return the exact configured issuer from discovery and assert acceptance; return the alternate slash form and assert rejection. Verify matching token iss values and configured JWKS URLs follow the same exact-identity policy.

---

### ISS-002-030 — DOCX ingestion loses paragraph/table order and heading context

1. **Description** — parse_docx() reads all document.paragraphs first and only afterwards reads document.tables. Interleaved tables are moved to the end and assigned generic root/Table N paths rather than the heading context at their actual position. Downstream chunks and documentation resources can therefore separate a table from the explanation that gives it meaning.

2. **Location & Evidence** — [`backend/app/parsers/documentation/docx.py`][src-054] — parse_docx() separate paragraph and table loops; [`backend/app/parsers/documentation/chunker.py`][src-001] — section-path-based chunking; [`backend/app/services/artifacts.py`][src-029] — documentation_resources().

3. **Criticality** — **Medium** — Source ordering and semantic context are corrupted during ingestion, reducing retrieval correctness.

4. **Recommended Solution** — Traverse DOCX body blocks in document order through the existing parser, maintaining the active heading stack while rendering both paragraphs and tables. Preserve current text/cell/block limits and handle nested supported blocks explicitly. Keep stable section identifiers and metadata that distinguish the table’s original context without introducing a second parser.

5. **Testing & Validation** — Create a DOCX with heading→paragraph→table→paragraph→next heading→table. Assert normalized sections, text, chunk order, and resource labels preserve that sequence and context. Cover empty paragraphs, merged cells, nested supported tables, text limits, and deterministic repeated parsing.

---

### ISS-002-031 — Warning-only source findings hide an otherwise valid canonical snapshot

1. **Description** — SourceService.metadata() uses an elif findings branch before elif snapshot is not None. Any findings enter that branch; with warnings/info only, parse_status becomes pending and snapshot-derived operation counts, servers, and authentication schemes are not populated. A successfully parsed source can consequently appear unfinished merely because it has nonblocking findings.

2. **Location & Evidence** — [`backend/app/services/sources.py`][src-004] — metadata() findings/snapshot branch order; [`backend/app/domain/sources.py`][src-007] — SourceVersionMetadataRecord; [`backend/app/schemas/source.py`][src-055] — SourceVersionMetadataRead.

3. **Criticality** — **Medium** — Operator-facing source status and configuration details can misrepresent successful parsing.

4. **Recommended Solution** — Compute parsing completion from the applicable canonical snapshot/stage evidence and compute finding severity independently. Populate valid snapshot metadata even when nonblocking findings exist, while preserving error findings and version/build attribution. Do not let warnings erase completion evidence or mark a source valid when its relevant parse actually failed.

5. **Testing & Validation** — Test valid snapshots with no findings, info-only findings, warning-only findings, and blocking errors, plus a genuinely pending source. Assert status and counts reflect parsing state while every finding remains visible and correctly attributed to the selected source version/build.

---

### ISS-002-032 — Semantically invalid AI review responses are cached as succeeded before validation

1. **Description** — SemanticReviewService saves a newly generated response with status="succeeded" before checking whether its findings reference known operation keys. If that semantic check fails, the saved row remains successful. A later attempt reuses the same response and repeats the failure instead of allowing a corrected provider response; the durable status also overstates validation success.

2. **Location & Evidence** — [`backend/app/services/analysis/review.py`][src-056] — review() _save() ordering, unknown-operation check, succeeded-response reuse; [`backend/app/repositories/builds.py`][src-022] — BuildAIRunRepository.create() preserves succeeded rows.

3. **Criticality** — **Medium** — One invalid model response can poison retry/reuse behavior and misstate durable evidence.

4. **Recommended Solution** — Perform all response-level semantic checks before recording success or making the result reusable. Persist a failed attempt with a safe reason when operation references are invalid, retaining permitted usage/cost evidence. Apply the same acceptance criteria when loading cached results, and reconcile historical invalid succeeded rows without treating them as valid build evidence.

5. **Testing & Validation** — Return a schema-valid review containing an unknown operation, then a valid response on retry. Assert the first result is not reusable success, the later valid response can be accepted, usage evidence remains accurate, and known-operation responses still reuse without an additional provider call.

---

### ISS-002-033 — Build diffs compare unstable provenance but omit effective server changes

1. **Description** — _operation_changes() compares server_ref rather than the referenced server definition, so a stable server key whose URL changes can evade the server change label. It also serializes parameter/response models including source references, causing version/provenance-only changes to appear as executable changes. The diff therefore risks both missing meaningful endpoint changes and overstating unchanged operation differences.

2. **Location & Evidence** — [`backend/app/services/builds/diff.py`][src-057] — _operation_changes(), _changed_mapping(), _serialized(); [`packages/contracts/src/mcp_contracts/canonical.py`][src-049] — CanonicalServer, CanonicalParameter, CanonicalResponse.

3. **Criticality** — **Medium** — Reviewers cannot reliably distinguish executable changes from provenance churn.

4. **Recommended Solution** — Define a deterministic semantic/executable projection for diffing within the existing diff service. Resolve effective server URL and relevant auth mappings, compare schema/transport behavior without incidental source-version IDs, and report provenance-only or enrichment-provenance changes separately where useful. Preserve true semantic changes and stable ordering.

5. **Testing & Validation** — Change only a project-default server URL with the same server key and assert an endpoint/server change. Change only source-version provenance and assert no false executable parameter/response change. Cover actual schema, method, path, security, and documentation changes with precise expected categories.

---

### ISS-002-034 — Concurrent cleanup target completion can leave aggregate job progress stale

1. **Description** — Each cleanup completion/failure locks its own target, then _refresh_job() aggregates target states and updates the parent job without first serializing parent aggregation. Two transactions completing different targets of the same job can each count before seeing the other’s commit; the later parent update can overwrite progress with an incomplete aggregate. A fully finished job may remain nonterminal until another refresh happens.

2. **Location & Evidence** — [`backend/app/repositories/cleanup.py`][src-058] — mark_completed(), mark_failed(), _refresh_job(); [`backend/app/models/cleanup.py`][src-059] — CleanupJob aggregate counters and status.

3. **Criticality** — **Medium** — Cleanup status, counters, and completion audit evidence can disagree with actual target outcomes.

4. **Recommended Solution** — Serialize aggregate refreshes on the existing parent job row using a consistent lock order, or use atomic counter transitions with a final authoritative aggregate. Ensure the calculation observes completed predecessor transactions and terminal timestamps/audit events are idempotent. Reconcile stale historical aggregates from their existing targets.

5. **Testing & Validation** — Complete two different targets of the same job concurrently using PostgreSQL transaction barriers. Assert exact counters and terminal status after both commits with no extra target operation required. Repeat with one failure, one skipped reference, duplicate completion, and concurrent retry.

---

### ISS-002-035 — Cleanup batches can outlive their leases before later targets begin processing

1. **Description** — CleanupWorker claims up to 100 targets with one lease expiry and then processes them sequentially. Slow earlier deletions can consume the entire lease before later targets start. Another worker may reclaim those targets while the first still holds them in memory, and processing/terminal updates do not check a matching claim owner. Retries and attempt counts can therefore advance independently of the intended execution.

2. **Location & Evidence** — [`backend/app/services/cleanup.py`][src-060] — process_due_targets_once(), _process(); [`backend/app/repositories/cleanup.py`][src-058] — claim_due_targets(), mark_completed(), mark_failed().

3. **Criticality** — **Medium** — Slow storage operations or multiple API processes can cause duplicate cleanup and unreliable recovery accounting.

4. **Recommended Solution** — Claim only bounded immediately executable work or renew each target’s existing lease while it is owned. Add claim/attempt fencing to target processing and completion so stale batches cannot update newer attempts. Preserve object-reference locking across deletion and apply equivalent protection to vector-generation reference checks where necessary.

5. **Testing & Validation** — Use a short lease, multiple targets, and a deliberately slow first deletion with two cleanup workers. Assert no stale owner finalizes a reclaimed target, attempt counts reflect actual attempts, referenced data is never removed, and eventual job totals remain correct after interruption and retry.

---

### ISS-002-036 — A retention-scheduling failure prevents processing unrelated pending cleanup

1. **Description** — dispatch_once() calls prepare_retention_once() before processing due cleanup targets and advances _next_retention_at only after success. A repeatable failure for one project aborts the cycle, leaving retention immediately due on every subsequent iteration. Pending source/project deletion and orphan cleanup are then never reached, even when their own operations are healthy.

2. **Location & Evidence** — [`backend/app/services/cleanup.py`][src-060] — dispatch_once(), prepare_retention_once(), run().

3. **Criticality** — **Medium** — One retention error can indefinitely block unrelated deletion and accumulate retained objects.

4. **Recommended Solution** — Isolate per-project retention scheduling failures and ensure due cleanup processing proceeds independently. Apply bounded retry/backoff to the existing retention scheduler, retain actionable error evidence, and advance or reschedule its next attempt deliberately. Keep deletion/reference transactions atomic and do not hide permanent failures.

5. **Testing & Validation** — Make retention preparation fail for one project while another has a due object-deletion target. Assert the deletion still completes, the failing project is retried on a bounded schedule, other projects continue scheduling, and logs/status expose the failure without a tight retry loop.

---

### ISS-002-037 — Application startup/shutdown does not guarantee bounded, complete resource cleanup

1. **Description** — The API constructs multiple clients before its lifespan try/finally and shuts down dispatchers sequentially without deadlines. An initialization exception after opening earlier clients can bypass cleanup. During shutdown, a stuck dispatcher or an exception from an earlier close prevents later tasks/clients from being stopped and closed.

2. **Location & Evidence** — [`backend/app/main.py`][src-027] — lifespan() client construction, dispatcher tasks, finally block; [`backend/app/jobs/build.py`][src-019] — _run() resource-finalization sequence.

3. **Criticality** — **Medium** — Partial startup and dependency outages can leak resources or hang service termination/redeployment.

4. **Recommended Solution** — Use structured lifetime management such as AsyncExitStack in the existing composition root, registering cleanup immediately after acquisition. Signal all dispatchers before awaiting them, apply bounded shutdown deadlines, cancel/join overdue tasks, and attempt every client close even if one fails. Keep the original startup/shutdown exception diagnosable without exposing secrets.

5. **Testing & Validation** — Inject failure after each client acquisition and assert every previously opened resource closes. Stall one dispatcher and make one close raise; assert shutdown completes within its configured bound and all remaining tasks/clients are cleaned up. Verify normal startup/shutdown and repeated application lifespans.

---

### ISS-002-038 — Redis clients omit explicit socket deadlines, including blocking queue operations

1. **Description** — Redis connections in the cache and both queue clients are created without explicit connection/read socket timeouts. Blocking queue calls run in asyncio.to_thread(); cancelling a readiness wait or awaiting coroutine does not itself terminate a stuck underlying thread/socket operation. Network failure can therefore occupy dispatchers or exhaust thread capacity beyond the intended request/readiness timeout.

2. **Location & Evidence** — [`backend/app/clients/cache.py`][src-061] — RedisClient.__init__(); [`backend/app/clients/build_queue.py`][src-062] — BuildQueueClient.__init__(), enqueue_build(), health(); [`backend/app/clients/queue.py`][src-025] — DeploymentQueueClient.__init__(), _enqueue(), health(); [`backend/app/api/health.py`][src-038] — _bounded_health().

3. **Criticality** — **Medium** — Network outages can leave internal work blocked despite higher-level timeout handling.

4. **Recommended Solution** — Configure explicit socket-connect/read deadlines and bounded retry behavior on the existing Redis clients, with validated settings and operational documentation. Ensure queue error normalization preserves retryability and rate-limit failures remain fail-closed. Align readiness deadlines with client-level bounds instead of relying only on cancelling an awaiting task.

5. **Testing & Validation** — Use an unreachable Redis endpoint and a server that accepts connections but never replies. Assert cache, health, enqueue, cancellation, and shutdown fail within their documented bounds, do not grow orphaned threads across repeated attempts, and recover cleanly when Redis returns.

---

### ISS-002-039 — Remote source fetches have no total deadline covering DNS, retries, redirects, and body streaming

1. **Description** — fetch_bounded() limits bytes, redirects, and attempt counts but uses per-operation HTTP timeouts rather than one overall deadline. URL policy DNS resolution occurs before the send try/timeout handling. A stalled resolver or an upstream that sends small chunks just within each read timeout can keep a fetch alive far beyond an expected bounded operation.

2. **Location & Evidence** — [`backend/app/clients/http.py`][src-063] — fetch_bounded(); [`backend/app/core/network_policy.py`][src-064] — resolve_addresses(), UrlPolicy.validate(); [`backend/app/services/sources.py`][src-004] — URL creation/refresh fetch calls.

3. **Criticality** — **Medium** — A remote source can tie up API work and resources without exceeding the byte limit.

4. **Recommended Solution** — Apply one validated wall-clock deadline to the complete existing fetch operation, including resolution, every redirect, retries/backoff, and body reads. Enforce a bounded resolver strategy and release responses/tasks on cancellation. Preserve IP pinning, TLS identity, byte limits, and redirect policy; return the existing normalized timeout error.

5. **Testing & Validation** — Test a resolver that stalls, a slow-drip body, repeated redirects, retryable failures with backoff, and cancellation during each phase. Assert a total elapsed-time bound, closed response streams, no persisted partial version, and successful ordinary fetches within the budget.

---

### ISS-002-040 — OpenRouter responses are fully buffered before any response-size limit is enforced

1. **Description** — _request_json_with_retries() calls the generic HttpClient.request(), which obtains the complete response before JSON parsing. There is no application response-byte limit for model catalogs, completions, or embeddings at that boundary. Input-context limits and later typed response validation do not prevent memory allocation for an oversized provider response.

2. **Location & Evidence** — [`backend/app/clients/ai.py`][src-032] — _request_json_with_retries(); [`backend/app/clients/http.py`][src-063] — request(); [`backend/app/providers/ai/openrouter.py`][src-065] — provider response normalization boundary.

3. **Criticality** — **Medium** — An erroneous or oversized provider response can consume worker/API memory before validation.

4. **Recommended Solution** — Add bounded streaming response consumption to the existing shared HTTP/client interface and select appropriate validated limits for catalog, completion, and embedding responses. Enforce declared and actual decoded byte limits before parsing, close streams on every outcome, and retain existing retries only for retryable failures. Do not reuse the source-fetch policy blindly for authenticated provider calls.

5. **Testing & Validation** — Return oversized bodies with correct, absent, and understated Content-Length, including compressed data. Assert early normalized rejection, bounded memory, closed streams, no successful AI-run evidence, and successful maximum-supported valid responses for each provider operation.

---

### ISS-002-041 — Password hashing blocks the asynchronous API event loop while database locks are held

1. **Description** — UserService.create(), update(), and bootstrap_first_admin() call the synchronous password hasher directly inside async methods and their database transactions. Expensive password hashing blocks the event-loop thread and extends email/admin mutation lock duration, delaying unrelated requests and concurrent administrative work.

2. **Location & Evidence** — [`backend/app/services/users.py`][src-066] — create(), update(), bootstrap_first_admin() password_hash expressions; [`backend/app/core/auth.py`][src-067] — PasswordManager.hash(), verify(), verify_and_update().

3. **Criticality** — **Medium** — CPU-heavy authentication work can degrade latency and lock contention under concurrency.

4. **Recommended Solution** — Move password hashing/verification into a bounded off-event-loop execution facility used by the existing authentication services. Compute expensive hashes outside database lock-holding transactions where safe, then revalidate mutation preconditions under the existing locks. Preserve the chosen password-hashing strength and prevent unbounded parallel hashing from exhausting memory.

5. **Testing & Validation** — Run concurrent user/password mutations while measuring an unrelated lightweight request. Assert event-loop responsiveness and bounded hashing concurrency, correct last-admin/email uniqueness enforcement, unchanged verification behavior, and no credential values in logs or exception responses.

---

### ISS-002-042 — Unbounded management collection reads grow with all retained records

1. **Description** — Several public collection paths return every matching record: users, projects, project access tokens, credentials, and build AI runs. Their repositories do not apply pagination, and AI-run reads load stored response JSON even though the API excludes it from the output DTO. Large histories therefore increase database transfer, allocation, serialization, and browser work without a bounded request contract.

2. **Location & Evidence** — [`backend/app/repositories/users.py`][src-068] — list(); [`backend/app/repositories/projects.py`][src-069] — list(); [`backend/app/repositories/mcp_access.py`][src-070] — list_tokens(); [`backend/app/repositories/credentials.py`][src-071] — list(); [`backend/app/repositories/builds.py`][src-022] — BuildAIRunRepository.list_for_build(), _ai_to_domain(); [`backend/app/api/builds.py`][src-043] — get_build_ai_runs().

3. **Criticality** — **Medium** — Legitimate growth can make management endpoints slow or memory-intensive.

4. **Recommended Solution** — Add bounded pagination and stable ordering to the existing endpoints/repositories and update their current frontend client contracts together. Select only needed columns for AI-run listing so excluded response payloads are never loaded for summaries. Preserve complete access through pagination rather than silently truncating records or introducing a second API version.

5. **Testing & Validation** — Seed large user/project/token/credential collections and a build with many large AI responses. Assert fixed maximum page size, complete nonduplicated traversal, stable tie-break ordering, bounded query payloads, and no hidden AI response hydration in summary requests. Verify current UI flows consume all pages they require.

---

### ISS-002-043 — Artifact-storage health reports success without verifying write capability

1. **Description** — FilesystemStorageClient.health() checks only whether the root exists and is a directory. It can report healthy on a read-only mount, with insufficient permissions, or when new writes fail. ready() includes this result in essential readiness, so the API can advertise readiness while every new upload/build artifact write fails.

2. **Location & Evidence** — [`backend/app/clients/storage.py`][src-072] — FilesystemStorageClient.health(); [`backend/app/api/health.py`][src-038] — ready() artifact_storage and ready_value.

3. **Criticality** — **Medium** — Readiness can misrepresent a dependency essential for successful mutations.

4. **Recommended Solution** — Use a small bounded create/write/flush/remove probe in the existing storage client, or an equivalently reliable capability check, without touching user artifacts. Handle read-only, permission, and capacity failures safely and clean the probe on all outcomes. Distinguish dependency capability reporting from per-request quota enforcement.

5. **Testing & Validation** — Check healthy, read-only, permission-denied, and full-capacity test filesystems. Assert correct readiness/dependency status within the timeout, no retained probe files, no modification of existing artifacts, and successful recovery after write capability is restored.

---

### ISS-002-044 — Backend log formatting has no central protection against sensitive exception/message content

1. **Description** — JsonLogFormatter writes record.getMessage() and the full formatted exception chain directly. The existing redact() utility is applied to audit metadata, not this logging boundary. Calls such as logger.exception() can therefore serialize arbitrary underlying exception text without a central secret-safety rule. This identifies a missing defense at a documented secret-handling boundary; it does not assert that a particular production secret was observed in logs.

2. **Location & Evidence** — [`backend/app/core/logging.py`][src-073] — JsonLogFormatter.format(), configure_logging(); [`backend/app/core/redaction.py`][src-074] — redact(); [`backend/app/services/cleanup.py`][src-060] — run() logger.exception(); [`backend/app/jobs/build.py`][src-019] — _heartbeat_admission() logger.exception(); [`SECURITY.md`][src-075] — secret-handling invariants.

3. **Criticality** — **Medium** — Unexpected exception content can bypass the project’s intended secret-safe observability contract.

4. **Recommended Solution** — Centralize safe structured logging using the existing logging/redaction facilities: controlled event names, allowlisted structured metadata, sanitized exception summaries, and explicit removal of sensitive URL/header/body values. Avoid blanket string substitution that destroys diagnostics or claims to detect every possible secret. Retain useful error types and trace correlation without serializing raw provider/request payloads.

5. **Testing & Validation** — Inject sentinel passwords, bearer tokens, API-key query parameters, and nested sensitive metadata into chained exceptions and log records. Assert sentinels do not reach console output, normal error categories/correlation remain visible, and malformed values cannot break JSON log emission.

---

### ISS-002-045 — Application cipher configuration cannot read prior encryption-key versions during rotation

1. **Description** — AesGcmSecretCipher supports a key mapping, but configured_secret_cipher()/from_base64_key() construct it with only the single configured key/version. Stored credentials and system secrets retain their individual key_version. Changing the active version through the current application configuration makes earlier records unreadable unless all of them were already reencrypted; the configured runtime has no multi-version transition capability.

2. **Location & Evidence** — [`backend/app/core/crypto.py`][src-076] — configured_secret_cipher(), AesGcmSecretCipher.from_base64_key(), decrypt_bytes(); [`backend/app/main.py`][src-027] — _cipher(); [`backend/app/jobs/build.py`][src-019] — _pipeline() cipher construction; [`backend/app/models/credential.py`][src-077] — key_version; [`backend/app/models/setting.py`][src-078] — SystemSecret.key_version.

3. **Criticality** — **Medium** — An operational encryption-key rotation can make retained credentials unavailable across API and workers.

4. **Recommended Solution** — Expose a validated key ring and active key version through the existing configuration/cipher boundary. Add a resumable re-encryption operation using the current associated-data rules and existing encrypted records; verify all records before retiring an old key. Update API/worker initialization and rotation documentation consistently, without changing encryption algorithms or creating duplicate secret storage.

5. **Testing & Validation** — Create records under key A, load A+B with B active, and assert old reads plus new writes work. Reencrypt with interruption/restart and verify idempotency, unchanged plaintext meaning, correct AAD rejection, and no secret logging. Remove A only after all required records can be decrypted under retained keys.

---

### ISS-002-046 — Refreshing activation proof after activation can invalidate rollback eligibility

1. **Description** — refresh_activation_proof() explicitly allows a RUNNING deployment and replaces activation_verified_at/proof while leaving activated_at unchanged. has_successful_activation() rejects a record when activated_at is earlier than activation_verified_at. A later successful proof refresh can therefore make a previously activated deployment appear never successfully activated for rollback checks.

2. **Location & Evidence** — [`backend/app/repositories/deployments.py`][src-013] — refresh_activation_proof(); [`backend/app/domain/deployments.py`][src-079] — has_successful_activation(), is_rollback_eligible().

3. **Criticality** — **Medium** — Refreshing valid runtime evidence can unexpectedly remove a legitimate rollback target.

4. **Recommended Solution** — Keep the original successful activation proof immutable once activation completes. Treat later health/runtime observations according to their separate meaning rather than replacing the proof used to establish historical activation. Reconcile repository updates and eligibility predicates so fresh observations cannot contradict activation history, and repair affected records only from retained trustworthy evidence.

5. **Testing & Validation** — Activate a deployment, create a later valid observation, refresh through the supported repository method, stop it, and evaluate rollback eligibility. Assert historical success remains valid, the content binding remains correct, and tampered proofs or never-activated deployments are still rejected.

---

### ISS-002-047 — The existing CLA workflow is an unfinished integration that always fails

1. **Description** — The CLA workflow’s only policy step ends with unconditional exit 1 and explicitly states that the verification service has not been connected. CONTRIBUTING.md documents the same placeholder. Thus every matching pull-request event fails this workflow regardless of the contributor’s actual status. This is an acknowledged integration gap, not a newly discovered legal requirement.

2. **Location & Evidence** — [`.github/workflows/cla.yml`][src-080] — policy job unconditional exit 1; [`CONTRIBUTING.md`][src-081] — CLA automation placeholder; [`CLA.md`][src-082] — unfinished verification integration statement.

3. **Criticality** — **Medium** — The repository cannot produce a meaningful successful result from an existing contribution workflow.

4. **Recommended Solution** — Replace the placeholder with the already intended configured verification integration and align the published instructions with its actual operation. Make the existing workflow report a truthful verified, unverified, or service-unavailable outcome with least-privilege permissions and no untrusted PR code execution. Do not introduce additional approval or authority workflows, bypass the stated policy, or change licensing as part of the technical correction.

5. **Testing & Validation** — Test representative verified/unverified contributor fixtures, unavailable verification service, fork pull requests, and repeated events. Assert accurate outcomes, no unconditional failure for verified fixtures, no secrets exposed to untrusted code, and documentation matching the configured integration.

---

### ISS-002-048 — Structured-output retries omit rejected-response usage and cost from build evidence

1. **Description** — structured_generate() receives a provider response and attempts schema validation before extracting or recording usage. Invalid structured content takes the continue branch, discarding any usage and cost included in that response. A later successful attempt returns only its own accounting; an all-failed review is saved with usage/cost=None. Reported provider consumption is therefore understated whenever a response consumes resources but fails validation. No particular live charge is alleged.

2. **Location & Evidence** — [`backend/app/providers/ai/openrouter.py`][src-065] — structured_generate() validation retry branch before _usage() and observe_openrouter_usage(); [`backend/app/services/analysis/review.py`][src-056] — review() failure persistence with usage/cost=None; [`backend/app/repositories/builds.py`][src-022] — BuildAIRunRepository.create() logical-run upsert.

3. **Criticality** — **Medium** — Retries can consume measurable resources while the existing operational evidence reports only the final accepted response or no usage at all.

4. **Recommended Solution** — Capture safe provider-supplied usage immediately after each received response, before content validation. Carry attempt-level and aggregate accounting through the existing typed provider result/error and existing AI-run evidence fields. Preserve known consumption on terminal failure, identify unavailable accounting explicitly rather than treating it as zero, and prevent cached reuse or repeated persistence from double-counting. Keep one accounting implementation and never persist secrets or raw rejected content solely for cost tracking.

5. **Testing & Validation** — Return an invalid structured response reporting 5 tokens and cost 0.002, followed by a valid response reporting 10 tokens and cost 0.003. Assert the logical run records 15 tokens and cost 0.005 with identifiable attempts. Verify all-failed runs preserve supplied usage, transport failures mark unknown accounting explicitly, cached reuse adds no provider consumption, and idempotent persistence does not double-count.

---

### ISS-002-049 — Inactive administrator records are incorrectly protected by the last-active-admin rule

1. **Description** — UserService.update() determines removes_admin from role and requested change without checking current.is_active. When only one active administrator exists, demoting or keeping disabled a different already-inactive administrator can be rejected as removal of the last active administrator even though the active administrator count would not decrease.

2. **Location & Evidence** — [`backend/app/services/users.py`][src-066] — update() removes_admin and count_active_admins() check; [`backend/app/repositories/users.py`][src-068] — count_active_admins(), lock_admin_mutations().

3. **Criticality** — **Low** — Administrative cleanup is blocked by an overly broad safety predicate; the actual last-admin protection is still necessary.

4. **Recommended Solution** — Compare the target’s current and proposed effective active-admin membership. Apply the protection only when the update removes a currently active administrator and would leave none. Retain the existing serialized admin-mutation lock and session-revocation behavior.

5. **Testing & Validation** — With one active admin and one inactive admin, demote/update the inactive record and assert success. Demoting/disabling the sole active admin must fail. Race changes to two active admins and assert at least one remains active after both requests.

---

### ISS-002-050 — OAuth token expiry validation accepts booleans and non-finite numbers

1. **Description** — OAuthTokenClient accepts expires_in when isinstance(value, int | float) and value > 0. Booleans pass that type test, NaN evades the <= 0 rejection, and Infinity is accepted then clamped. Such values are not meaningful token lifetimes and can produce incorrect cache-expiry or repeated-refresh behavior.

2. **Location & Evidence** — [`mcp_runtime/app/clients/oauth_client.py`][src-083] — fetch_client_credentials() expires_in validation and OAuthAccessToken construction.

3. **Criticality** — **Low** — Malformed provider metadata is accepted instead of producing a controlled authentication failure.

4. **Recommended Solution** — Require a non-boolean finite positive numeric lifetime before applying the documented upper bound. Keep token-value/header-safety validation aligned with the existing authentication boundary and handle omitted expiry according to an explicit policy rather than malformed-number coercion.

5. **Testing & Validation** — Test expires_in as true, false, NaN, Infinity, negative, zero, string, omitted, integer, and fractional finite positive value. Assert malformed inputs fail safely, valid lifetimes produce finite bounded cache deadlines, and no invalid response is reused as a valid token.

---

### ISS-002-051 — Structured backend logging silently drops emitted lifecycle correlation fields

1. **Description** — JsonLogFormatter preserves a fixed context_fields tuple. Cleanup and runtime-command logs emit cleanup_target_id, cleanup_job_id, runtime_command_id, retryable, and admission_attempt, but these names are not in that tuple. These useful identifiers disappear from production JSON logs even though the calling services supplied them.

2. **Location & Evidence** — [`backend/app/core/logging.py`][src-073] — JsonLogFormatter.context_fields; [`backend/app/services/cleanup.py`][src-060] — _process() logger.warning(); [`backend/app/services/deployment/command_executor.py`][src-024] — run() logger.warning(); [`backend/app/services/build_admission.py`][src-084] — dispatch_once() logger.warning().

3. **Criticality** — **Low** — Operational troubleshooting loses the identifiers needed to correlate a failure with durable work.

4. **Recommended Solution** — Define a shared typed/allowlisted logging context for the existing services and add the non-sensitive identifiers actually emitted by lifecycle and cleanup code. Normalize naming across emitters and formatters, validating JSON-safe values without allowing arbitrary payload logging. Address secret sanitization through the separate logging-safety finding.

5. **Testing & Validation** — Capture JSON logs from failed build admission, cleanup, and runtime-command execution. Assert their job/command/target IDs and safe retry fields are present, stable, and correctly typed; unknown or sensitive fields remain excluded and serialization cannot fail on unsupported values.

---

### ISS-002-052 — The Git ignore rules hide newly added authoritative documentation

1. **Description** — The repository ignores docs/ wholesale while contribution/governance documentation identifies files under docs/ as authoritative. Already tracked files remain tracked, but newly created operational, schema, or verification documents under that directory are silently ignored unless explicitly forced into Git.

2. **Location & Evidence** — [`.gitignore`][src-085] — docs/ pattern; [`CONTRIBUTING.md`][src-081] — engineering and documentation update requirements; [`GOVERNANCE.md`][src-086] — authoritative docs reference.

3. **Criticality** — **Low** — Required documentation additions can be omitted from ordinary commits and reviews.

4. **Recommended Solution** — Remove the blanket docs/ exclusion and ignore only identified generated documentation/cache outputs. Preserve existing tracked documentation and verify that any generated assets requiring exclusion have precise patterns. Do not move authoritative documentation into a competing tree.

5. **Testing & Validation** — Create a temporary representative operational Markdown file and run git check-ignore/status. Assert it is visible for normal version control, existing generated caches remain ignored, and no secrets or local build artifacts become unintentionally trackable.

---

### ISS-002-053 — The checked-in checksum manifest references a file absent from the reviewed tree

1. **Description** — MANIFEST.sha256 contains an entry for ./AGENT3_HANDOFF.md, but that path is absent from the reviewed root tree. A full checksum verification therefore cannot succeed against this snapshot. The manifest’s intended coverage/freshness is not self-consistent with the actual repository inventory.

2. **Location & Evidence** — [`MANIFEST.sha256`][src-087] — ./AGENT3_HANDOFF.md entry. Inventory evidence: [reviewed root tree](https://github.com/yazeedhasan97/MCPlica/tree/090ec0a82bf6689c9764716afdd20409c366d178).

3. **Criticality** — **Low** — Integrity/reproducibility evidence contains a demonstrably stale inventory entry.

4. **Recommended Solution** — Regenerate the existing manifest from its explicitly defined tracked/release input set, excluding the manifest itself and intentional non-input artifacts. Remove absent entries and verify every retained checksum. Document whether it describes the source snapshot or a release bundle and update the existing generation/check command accordingly.

5. **Testing & Validation** — Run checksum verification against a clean checkout of the corrected snapshot and assert no missing, mismatched, duplicate, or unintended entries. Add/remove a representative covered file and assert the manifest check detects the change. Verify generation is deterministic.

---

### ISS-002-054 — The Makefile runtime-build target produces a different image tag from the default deployment configuration

1. **Description** — make runtime-build tags the image mcplica/mcp-runtime:dev, while .env.example configures MCP_RUNTIME_IMAGE=mcplica/mcp-runtime:1.0.0. Running the named build target does not create the image the default deployment configuration selects, which can lead to an unexpected pull or missing-image failure.

2. **Location & Evidence** — [`Makefile`][src-088] — runtime-build target; [`.env.example`][src-041] — MCP_RUNTIME_IMAGE and MCP_RUNTIME_VERSION; [`infra/compose.yaml`][src-034] — runtime-validator image/build configuration.

3. **Criticality** — **Low** — Local image preparation and configured deployment behavior are inconsistent.

4. **Recommended Solution** — Make the existing target resolve and build the same configured development image reference/version used by Compose and deployment, with one documented default. Keep production digest requirements intact and do not attempt to build into an immutable digest reference. Avoid maintaining separate hardcoded image names across commands.

5. **Testing & Validation** — With the example development configuration, run the target and assert the selected image exists and is used without an unintended registry pull. Repeat with a supported custom tag/version. Assert production digest configuration remains validated and is not silently replaced with a mutable development tag.

---

### ISS-002-055 — The example environment file defines MCP_RUNTIME_VERSION twice

1. **Description** — MCP_RUNTIME_VERSION appears once in Docker/deployment configuration and again in the runtime example block. The values currently match, but editing only one produces an ambiguous example whose effective value depends on loader duplicate-key behavior. This increases configuration drift between builder, validator, and deployed runtime.

2. **Location & Evidence** — [`.env.example`][src-041] — both MCP_RUNTIME_VERSION assignments.

3. **Criticality** — **Low** — A small configuration-maintenance defect can cause hard-to-diagnose version mismatches.

4. **Recommended Solution** — Keep one authoritative assignment and refer to it from comments in other sections. Add duplicate-name validation for the example environment file in the existing configuration checks, without adding a deployment-time test step or changing established variable names.

5. **Testing & Validation** — Parse assignment names from .env.example and assert uniqueness. Change the single runtime version in a test fixture and verify all documented consumers resolve it consistently. Confirm comments and blank optional values do not trigger false positives.


[src-001]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/parsers/documentation/chunker.py
[src-002]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/clients/vector.py
[src-003]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/providers/milvus.py
[src-004]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/services/sources.py
[src-005]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/repositories/sources.py
[src-006]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/models/source.py
[src-007]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/domain/sources.py
[src-008]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/domain/builds.py
[src-009]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/models/build.py
[src-010]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/services/canonicalization/service.py
[src-011]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/services/builds/configuration_identity.py
[src-012]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/services/deployment/service.py
[src-013]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/repositories/deployments.py
[src-014]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/services/credentials.py
[src-015]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/services/mcp_access.py
[src-016]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/services/deployment/preflight.py
[src-017]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/packages/contracts/src/mcp_contracts/runtime_secrets.py
[src-018]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/repositories/build_admission.py
[src-019]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/jobs/build.py
[src-020]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/services/builds/pipeline.py
[src-021]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/services/builds/service.py
[src-022]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/repositories/builds.py
[src-023]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/repositories/runtime_commands.py
[src-024]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/services/deployment/command_executor.py
[src-025]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/clients/queue.py
[src-026]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/infra/docker/nginx.conf
[src-027]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/main.py
[src-028]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/infra/compose.production.yaml
[src-029]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/services/artifacts.py
[src-030]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/mcp_runtime/app/core/config.py
[src-031]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/mcp_runtime/app/main.py
[src-032]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/clients/ai.py
[src-033]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/services/settings.py
[src-034]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/infra/compose.yaml
[src-035]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/services/projects.py
[src-036]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/schemas/setting.py
[src-037]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/api/sources.py
[src-038]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/api/health.py
[src-039]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/infra/docker/backend.Dockerfile
[src-040]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/clients/runtime_files.py
[src-041]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/.env.example
[src-042]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/schemas/build.py
[src-043]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/api/builds.py
[src-044]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/domain/credentials.py
[src-045]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/schemas/credential.py
[src-046]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/services/deployment/secret_materializer.py
[src-047]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/services/builds/readiness.py
[src-048]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/services/builds/credential_mapping.py
[src-049]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/packages/contracts/src/mcp_contracts/canonical.py
[src-050]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/packages/contracts/src/mcp_contracts/inventory.py
[src-051]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/parsers/api_inventory/parser.py
[src-052]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/mcp_runtime/app/executor/response_contract.py
[src-053]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/mcp_runtime/app/clients/oidc_client.py
[src-054]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/parsers/documentation/docx.py
[src-055]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/schemas/source.py
[src-056]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/services/analysis/review.py
[src-057]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/services/builds/diff.py
[src-058]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/repositories/cleanup.py
[src-059]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/models/cleanup.py
[src-060]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/services/cleanup.py
[src-061]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/clients/cache.py
[src-062]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/clients/build_queue.py
[src-063]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/clients/http.py
[src-064]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/core/network_policy.py
[src-065]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/providers/ai/openrouter.py
[src-066]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/services/users.py
[src-067]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/core/auth.py
[src-068]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/repositories/users.py
[src-069]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/repositories/projects.py
[src-070]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/repositories/mcp_access.py
[src-071]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/repositories/credentials.py
[src-072]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/clients/storage.py
[src-073]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/core/logging.py
[src-074]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/core/redaction.py
[src-075]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/SECURITY.md
[src-076]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/core/crypto.py
[src-077]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/models/credential.py
[src-078]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/models/setting.py
[src-079]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/domain/deployments.py
[src-080]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/.github/workflows/cla.yml
[src-081]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/CONTRIBUTING.md
[src-082]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/CLA.md
[src-083]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/mcp_runtime/app/clients/oauth_client.py
[src-084]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/backend/app/services/build_admission.py
[src-085]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/.gitignore
[src-086]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/GOVERNANCE.md
[src-087]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/MANIFEST.sha256
[src-088]: https://github.com/yazeedhasan97/MCPlica/blob/090ec0a82bf6689c9764716afdd20409c366d178/Makefile
