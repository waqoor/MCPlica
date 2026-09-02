# Foundation consistency and lifecycle closure

- Date: 2026-09-02
- Implementation baseline: `708401dc47a7684c8c95ab0e4061d595657c57dc`
- Scope: `ISS-002-002` through `ISS-002-009` in `issues_002.md`

## Outcome

All eight foundation findings were reproduced against the baseline, corrected in the existing
source, Build, deployment, runtime-command, and indexing paths, and exercised through unit,
PostgreSQL concurrency, real Milvus, Linux Docker, Compose, API, MCP, and browser boundaries. They
are closed in repository scope.

The fixes do not create alternate pipelines, queues, or deployment paths. PostgreSQL remains the
durable source of truth; Redis remains a delivery/wake-up mechanism; Build and runtime effects use
the established workers; and an immutable READY Build remains the only deployable artifact.

"Closed" does not claim deployment to an external production host, live OpenRouter use, production
DNS/TLS, operator backup restoration, image signing, or release promotion. Those environment-owned
release gates remain explicit in the release checklist.

## Finding dispositions

### `ISS-002-002` — explicit current source selection

Migration `0021_source_selection_and_build_bindings` adds a same-source `current_version_id`
reference plus accepted-observation time and HTTP validator state. Source/project locking now makes
selection, observation metadata, audit, and immutable version creation/reuse one transaction.
Summary, discovery, Build binding, conditional refresh, and retention all read the explicit
selection rather than inferring "current" from version creation order.

Proof includes `test_hash_reuse_restores_current_source_version_and_validators`, which runs
A→B→A and verifies that A is selected again without rewriting its immutable row;
`test_concurrent_source_observations_commit_in_serialized_acceptance_order`; compound source
creation/retry/primary-switch recovery; 304 validator reuse; historical Build preservation; and
retention protection in `backend/tests/integration/test_source_lifecycle_postgres.py`.

### `ISS-002-003` — immutable executable source identity

Each Build/source binding now freezes source ID, kind, name, origin, URL, source creation time,
primary role, and dependency aliases. Configuration hashing and canonicalization consume that
frozen binding, so renaming a source or promoting a different primary after queueing cannot change
the queued Build. Migration-backfilled bindings whose original role/aliases cannot be proven are
marked untrustworthy and cannot be newly activated until rebuilt.

Proof includes `test_configuration_fingerprint_includes_frozen_role_name_and_aliases`, queued-Build
canonicalization after live source mutation, stale configuration preflight, historical trust
checks, and PostgreSQL source lifecycle cases in `test_canonicalization_reads.py`,
`test_build_request_readiness.py`, `test_deployment_request_preflight.py`, and
`test_source_lifecycle_postgres.py`.

### `ISS-002-004` — transition-aware stop-first replacement

Deployment replacement now assigns a transition identity and excludes only the STOPPING rows
created by that same project-locked transition. Unrelated deployments remain conflicts. The
durable STOP command is the DEPLOY command's predecessor, and claim/execution rechecks prevent the
replacement from overtaking a pending or failed stop.

Proof includes `test_stop_first_transition_commits_ordered_stop_then_security_refresh`, unrelated
work exclusion, duplicate/reordered delivery, predecessor failure, and retry/replay cases in
`test_foundation_lifecycle_postgres.py`, `test_runtime_command_postgres.py`, and
`test_runtime_command_lifecycle.py`.

### `ISS-002-005` — final verifier revocation

Final static-token revocation is evaluated under the project lock and commits the revocation with
one durable STOP command. It does not try to materialize an invalid replacement and does not restore
the revoked verifier. Repeated revocation is idempotent, while API state distinguishes requested,
effective, and failed lifecycle effect.

Proof includes `test_final_token_revocation_commits_one_stop_and_no_invalid_replacement`, subset,
expired-token, duplicate-request, queue restart, stop failure, and exact observed-effect cases in
`test_foundation_lifecycle_postgres.py`, `test_mcp_runtime_security.py`, and
`test_runtime_command_lifecycle.py`.

### `ISS-002-006` — narrowly scoped security refresh

Migration `0023_deployment_intent` persists `normal`, `security_refresh`, and `rollback` intent.
Authentication-only maintenance remains bound to the exact active immutable Build and may bypass
only unrelated pending source identity. Artifact integrity, project ownership, runtime
compatibility, and current secret material remain mandatory. Unsafe rematerialization produces a
durable STOP instead of rolling back the security mutation or deploying another Build.

Proof includes `test_security_refresh_ignores_source_drift_but_normal_deploy_does_not` and
`test_unsafe_security_refresh_commits_a_stop_instead_of_rolling_back`, plus credential/token
rotation and deployment-preflight cases. These prove source B is never activated implicitly and a
normal attempt to reactivate stale Build A still fails.

### `ISS-002-007` — cancellation acknowledgement and recovery

A cancellation request no longer silently destroys a live owner's ability to acknowledge it. The
current owner acknowledges through the canonical idempotent cancellation/cleanup transaction at a
pipeline boundary. If the owner has died or its lease expires, admission recovery claims the
cancellation specifically and finalizes it without executing another pipeline stage. Only the
exact admission owner can release its claim.

Proof includes `test_cancellation_is_request_then_effective_acknowledgement`,
`test_cancelled_build_keeps_live_owner_and_dead_owner_is_recovered`, duplicate acknowledgement,
queue failure, long-stage cancellation, cleanup capture, and admission of the subsequent Build in
`test_build_cancellation_postgres.py`, `test_build_admission_postgres.py`, and
`test_build_state.py`.

### `ISS-002-008` — Build execution fencing

The admission token is carried through the canonical Build pipeline. Every accepted stage,
terminal state, validation, AI-run/accounting, artifact, and index-generation publication checks
the exact live token. The heartbeat uses a monotonic local deadline derived from the last
database-confirmed lease and stops external work after ownership can no longer be proven.

Migration `0025_index_generation_execution_fencing` binds a Build-created generation to its
accepted execution token. Milvus physical row identity and retrieval include that attempt token,
while canonical chunk identity and embedding-cache identity retain their deterministic meanings.
Cleanup by a stale attempt therefore cannot remove a replacement owner's rows.

Proof includes `test_reclaimed_build_rejects_every_stale_result_writer`, heartbeat outage and
normal-renewal cases, AI/accounting and validation fencing, and
`test_vector_rows_and_queries_are_fenced_to_the_execution_owner`. The real Milvus acceptance check
also wrote identical logical chunks through two attempts, removed the stale attempt, and verified
that the accepted replacement remained searchable.

### `ISS-002-009` — runtime-command execution fencing

Migration `0022_runtime_command_execution_fencing` adds a fresh token for each command execution
claim. Queue payload, PostgreSQL-time renewal, ownership checkpoints, deployment-state mutations,
and terminal command writes all use that exact token. The executor stops at the last confirmed
monotonic lease deadline and holds a PostgreSQL session advisory project lock around Docker
effects. STOP targets the deployment's exact recorded container ID, never a reusable name, and
predecessor effectiveness is rechecked after every reclaim.

Proof includes project-lock serialization and outbox restart cases in
`test_runtime_command_postgres.py`; successful renewal, rejected-token cancellation, database
outage, idempotent replay, and observed-stop effectiveness cases in
`test_runtime_command_lifecycle.py`; and the real Linux Docker runtime
isolation/replacement/rollback acceptance.

## Migration and compatibility result

The single linear Alembic head advances from `0020` to `0025`:

- `0021` adds explicit source selection/observation state and immutable Build/source bindings. Its
  downgrade refuses to discard an A→B→A selection that the old schema cannot represent.
- `0022` adds runtime-command execution fencing and safely requeues live pre-fencing attempts.
- `0023` adds deployment intent and backfills existing rows as `normal`.
- `0024` fences cleanup attempts; it is part of the same linear head and shares the worker-safety
  model, although its originating finding is outside this eight-issue slice.
- `0025` binds Build index generations and Milvus rows to the accepted execution owner.

A blank PostgreSQL database upgraded through every revision to the unique `0025` head. ORM drift
checking reported no new operations. Upgrade/downgrade/re-upgrade behavior and historical
constraint-name compatibility are covered in `test_schema_drift_postgres.py`; unrepresentable
source-selection loss fails closed rather than being silently corrupted.

## Verification record

The final manifest-bound aggregate count is recorded here after the final integrity pass. All
entries below were executed against the same staged implementation before commit.

| Boundary | Verified result |
| --- | --- |
| Backend/contracts/fixture tests, including PostgreSQL | 381 passed, 2 environment-gated skips; all 26 critical coverage floors passed |
| Focused PostgreSQL foundation/concurrency set | 40 passed |
| Runtime unit/protocol/security | 69 passed |
| Frontend unit/API | 37 files, 154 passed |
| Frontend lint, strict typecheck, production build, formatting, generated API drift, asset budgets | Passed |
| Backend/runtime/integration Ruff and strict Pyright | Passed; 0 type errors |
| Alembic upgrade/current/check | `0025 (head)`; no ORM drift |
| Real Milvus isolation/attempt cleanup | Passed |
| Real Linux Docker runtime isolation/replacement/rollback | 1 passed |
| Canonical Compose service-state/health evidence | 11 long-running services healthy; both one-shot jobs exited 0 |
| Full source→Build→deploy→update→redeploy→rollback→MCP workflow | Passed in 126.903 s; both Builds 100% coverage; 4→5→4 tools |
| Runtime MCP call while builder unavailable | Passed, 0.424 s round trip |
| Container recreation persistence | Passed |
| Live Chromium workflow | 1 passed |
| Python frozen dependency audit | No known vulnerabilities found |
| Frontend production dependency audit | No vulnerabilities found at high/critical threshold |
| Repository vulnerability/misconfiguration/secret scan | Trivy 0.74 staged-index scan: 0 HIGH/CRITICAL vulnerabilities, 0 misconfigurations, 0 secrets; policy exit 0 |
| Deterministic tracked-source checksum manifest | Regenerated from the final tracked-source set and verified before commit |

The full-stack run produced two READY Builds, three successful deployment events (initial,
replacement, rollback), one-operation diff growth, a readable documentation resource, an exported
five-file bundle, runtime continuity during builder outage, and durable state after container
recreation. Fixture upstreams and an offline/degraded OpenRouter configuration were intentional;
no provider credential was fabricated and this local evidence is not presented as live provider
certification.

## Operational behavior

- Operators may restore historical source bytes; the accepted selection changes immediately while
  immutable version history and old Build bindings remain unchanged.
- Cancellation remains "requested" until a worker or expired-owner recovery durably acknowledges
  it. Manual token/lease edits are not a recovery procedure.
- Security refresh never promotes a newer source implicitly. If current auth cannot safely support
  the active Build, the security change is retained and the runtime is stopped.
- Final-verifier revocation is effective only after the durable STOP effect is observed; queue or
  worker failure remains visible and retryable rather than being reported as success.
- Reclaimed Build/runtime attempts cannot publish state for their successors. Operators should
  recover the canonical worker/queue and allow token-fenced reconciliation to run.

See `docs/operations/runbook.md`, `docs/operations/upgrade.md`,
`docs/security/threat-model.md`, and `docs/release/release-checklist.md` for recovery, migration,
threat, and environment-owned release gates.
