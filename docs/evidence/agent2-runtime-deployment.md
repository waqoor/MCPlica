# Agent 2 runtime and deployment evidence

> Historical workstream snapshot. Image digests, counts, and concurrent-boundary notes
> below describe that partial stream at handoff time. The reconciled repository-wide
> result is authoritative in `final-integrated-validation.md`.

**Validated:** 2026-08-26  
**Scope:** generic MCP runtime, runtime security, MCP validation/access, dynamic Docker
deployment, deployment persistence/jobs/APIs/migrations, and the directly supporting
infrastructure.

## Requirement traceability

| Requirement | Repository implementation | Acceptance evidence |
| --- | --- | --- |
| FR-MCP-001/002/003 | `mcp_runtime/app/server/factory.py`, `tool_registry.py`, and `resource_registry.py` publish exact manifest schemas, Streamable HTTP `/mcp`, and bounded resource pagination through the official MCP SDK. | Runtime protocol/auth and executor acceptance tests pass. |
| FR-MCP-004/006 | `executor/request_builder.py`, `executor/executor.py`, and `clients/api_client.py` deterministically serialize path/query/header/body/multipart mappings; destinations and credentials cannot come from caller arguments. | Request-builder, executor, URL-policy, and upstream-auth negative tests pass. |
| FR-MCP-005 | The runtime package has no OpenRouter, Milvus, PostgreSQL, Redis, Docker SDK, or builder-service dependency/import. | Dependency/import sweep is empty and the standalone runtime image builds from the frozen lock. |
| FR-MCP-007/008 | Runtime HTTP/OAuth/OIDC clients apply connect/read/write/pool plus whole-operation deadlines, bounded request/response/JWKS sizes, no redirects/proxy inheritance, stable redacted MCP errors, and bounded structured logs. | API/OAuth/OIDC/error acceptance tests pass, including cumulative streaming limits. |
| FR-SEC-004/005/006/007 | `auth/inbound.py` separates inbound authentication from upstream credentials, implements constant-time static-token hash verification, and validates OIDC issuer/audience/algorithm/expiry/scopes with bounded JWKS refresh. Production rejects anonymous mode. | Static and OIDC positive/negative protocol tests pass; `no-store`, `no-cache`, and `max-age=0` do not reuse keys. |
| FR-SEC-008/009 | `auth/upstream.py`, `clients/oauth_client.py`, and the shared typed secret contract support bearer, API-key header/query, Basic, OAuth client credentials, and static secret headers without putting plaintext in manifests, labels, responses, or routine logs. | Credential-shape, injection, redaction, missing-secret, and OAuth cache tests pass. |
| SSRF/DNS rebinding boundary | `security/url_policy.py` admits only exact configured origins/hosts and allowed schemes/ports, rejects userinfo/fragments/private/link-local/loopback/metadata by default, bounds DNS answers, and `clients/pinned_transport.py` connects to the exact validated address while preserving hostname TLS/SNI and pooling. Remote JSON-Schema references are rejected before validator construction. | Tests prove private/redirect/host-override rejection, safe-first/private-second rebinding rejection at socket connect, exact IP pinning, and local-only schema references. |
| Safe runtime inputs | `manifest/loader.py` and `secrets/loader.py` use bounded `O_NOFOLLOW` reads, require regular files and exact hashes/types, and enforce owner/mode checks for secrets. Runtime configuration has fail-closed production invariants. | Manifest/secret/config security tests pass; Windows bind permissions were correctly rejected rather than weakened. |
| FR-DEP-001/002/003/004/005/009 | `DockerClient`, `RuntimeManager`, `RuntimeFilesClient`, and Compose create dynamic per-project networks/containers, explicit non-secret Traefik labels, read-only mounts/rootfs, non-root UID, cap-drop, no-new-privileges, bounded CPU/memory/PIDs/tmpfs/logs, and no builder network/socket access. | Final-image real-Docker test proves two concurrent isolated projects and inspects/reuses only exact managed resources. Runtime image is non-root and health-checked. |
| FR-DEP-006/007 | `DeploymentService`/`DeploymentRunner` lock project state, validate immutable READY artifacts, materialize only required secrets, health-check a replacement before activation, preserve the healthy prior deployment on failure, and implement stop/restart/redeploy/rollback as new deployment events. | Unit/state/race tests plus real-Docker healthy replacement and rollback pass. |
| FR-DEP-008 | API services enqueue durable work; only `deployment-worker` constructs `DockerClient` and receives the Docker socket. Builder and deployment queues are separate and use bounded RQ retry scheduling. | Compose/API dependency inspection and deployment job tests pass. |
| MCP access lifecycle | `MCPAccessService`, repository/models, and `/api/v1` access routes implement production-safe auth-mode configuration plus one-time static-token issue/rotate/revoke using hashes only. Security-impacting mode/revocation changes queue runtime stop/replacement. | Access authorization, one-time disclosure, rotation/revocation, audit, and deployment coupling tests pass. |
| Persistence and upgrade | Migration `0007_deployments_mcp_access.py` adds deployment/access state and constraints; `0008` remains the single integrated head. `migrations/alembic/env.py` uses a Selector event loop for async Psycopg only on Windows. | Offline SQL renders and a fresh PostgreSQL 18.6 database upgrades `0001 -> ... -> 0008 (head)`. |
| Async/scalable boundaries | Blocking Docker SDK calls are isolated with `asyncio.to_thread`; HTTP/MCP clients reuse bounded pools; services use async repositories, deterministic pagination, locks, batching, and bounded retry/concurrency. | Strict typing is clean and concurrency/race/retry tests pass. |

No V2 route, duplicate model/service, compatibility layer, alternate persistence/execution
path, canary/shadow flow, generated per-project app, or microservice split was introduced.

## Final local verification

| Gate | Result |
| --- | --- |
| Runtime quality/tests | Ruff and format clean; strict Pyright `0 errors`; `36 passed`. |
| Backend behavior | `72 passed, 1 skipped` in the ordinary suite. The skip is the explicit Docker-enabled acceptance, which passed separately. |
| Backend quality | Full Ruff clean; full strict Pyright `0 errors`; all 18 Agent 2 runtime/deployment files format-clean. |
| Shared contracts | Ruff/format/Pyright clean; `2 passed`; regenerated JSON Schemas have no drift. |
| Real Docker lifecycle | Final image: `1 passed in 34.15s`; two projects, isolated networks, healthy replacement, rollback, unaffected peer, and cleanup. |
| Runtime image | Frozen build succeeded as `sha256:1c5de64e4fc46add85f08dfe28de7f7ebaedb159484084a0beb463f817ea743a`; user `10001:10001`; `/readyz` healthcheck. |
| Database migration | Single `0008` head; offline SQL passed; fresh PostgreSQL upgrade reached `0008 (head)`. |
| Infrastructure | Development and production Compose render cleanly; CI YAML parses; runtime/backend frozen image builds passed. |
| Hygiene | `git diff --check` passed; no merge markers, owned production TODO/FIXME/stub markers, forbidden runtime dependencies, or leftover Agent 2/managed Docker resources. |

The Docker acceptance uses a Linux named volume because Docker Desktop cannot represent a
Linux `0600` owner contract on a Windows bind mount. The insecure bind was rejected by the
runtime as designed; no permission check was relaxed.

## Concurrent integration boundary

Shared changes were unavoidable only where the canonical contract crosses workstreams:

- shared manifest/runtime-secret types and generated schemas;
- project active build/deployment references and the linear `0007 -> 0008` migration chain;
- backend dependency construction/router/project lifecycle hooks needed to enqueue deployment
  stop/replacement work;
- root lock, CI, Dockerfiles, Compose, example configuration, and operations/security docs.

At final validation, repository-wide backend formatting still reported seven concurrently owned
Agent 1 files: `app/core/async_utils.py`, `app/services/analysis/reuse.py`,
`app/services/builds/service.py`, `tests/test_async_utils.py`,
`tests/test_build_pipeline_components.py`, `tests/test_openapi_compiler.py`, and
`tests/test_semantic_reuse.py`. Agent 2 did not edit or duplicate that work; its complete owned
surface is format-clean.

## Promotion-only gates

Repository behavior is complete. Production certification still requires target-environment
values and evidence: immutable registry digests, real DNS/ACME/TLS, unique secrets and external
OIDC metadata, a constrained Docker socket proxy where supported, hosted CI/security results,
and live monitoring/backup/restore/rollback drills. These are deployment gates, not production
TODOs or mock implementations.
