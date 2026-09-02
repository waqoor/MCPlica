# `issues_002.md` implementation and verification closure

- Date: 2026-09-02
- Implementation baseline: `708401dc47a7684c8c95ab0e4061d595657c57dc`
- Scope: all 55 findings in the root `issues_002.md`

## Outcome

Every finding was reproduced against its cited contract or regression scenario and then
rechecked against the implementation baseline. Twelve findings were already correctly remediated
in that checkout and were retained and regression-tested. The remaining 43 findings were
applicable and were corrected in the existing canonical architecture. No finding was dismissed as
inapplicable, and no issue remains open in repository scope.

"Closed" here means the source, schema, generated contracts, tests, and local runtime/Compose
boundaries are complete. It does not claim deployment to an external production host, possession
of an operator's OpenRouter credential, or installation of the operator-selected CLA service.
Those integrations remain fail-closed until their documented production configuration is supplied.

## Per-finding disposition and evidence

| Finding | Baseline applicability | Final disposition | Primary implementation and verification evidence |
| --- | --- | --- | --- |
| `ISS-002-001` | Already remediated | Closed, verified | Scoped chunk identity in `parsers/documentation/chunker.py` and Milvus generation filters; `test_chunk_identity.py`, `test_vector_store.py`, and `vector_isolation_check.py`. |
| `ISS-002-002` | Applicable | Closed, fixed | Explicit immutable current-version selection and observation metadata in migration `0021`, source model/repository/service; A-B-A, 304, concurrency, retention, and Build-binding cases in `test_source_lifecycle_postgres.py`. |
| `ISS-002-003` | Applicable | Closed, fixed | Frozen source role/name/origin/URL/dependency aliases in migration `0021`, configuration identity, and canonicalization; `test_canonicalization_reads.py`, `test_build_request_readiness.py`, and source lifecycle integration. |
| `ISS-002-004` | Applicable | Closed, fixed | Transition-aware stop-first conflict handling and ordered predecessor commands in deployment service/repositories; `test_foundation_lifecycle_postgres.py` and runtime-command suites. |
| `ISS-002-005` | Applicable | Closed, fixed | Final-verifier revocation commits one durable STOP without an invalid replacement in MCP access/deployment services; MCP runtime security and foundation PostgreSQL tests. |
| `ISS-002-006` | Applicable | Closed, fixed | Persisted `security_refresh` intent in migration `0023`, exact-active-Build maintenance and fail-safe STOP; deployment preflight/request and foundation integration tests. |
| `ISS-002-007` | Applicable | Closed, fixed | Live-owner cancellation acknowledgement plus dead-owner recovery in build admission, cancellation service, job, and pipeline; build cancellation/admission PostgreSQL tests. |
| `ISS-002-008` | Applicable | Closed, fixed | Exact admission-token checks on all accepted Build/stage/result/AI/artifact/index writes, deadline-bound heartbeat, and migration `0025`; pipeline-stage PostgreSQL and vector-store tests. |
| `ISS-002-009` | Applicable | Closed, fixed | Runtime-command execution token, renewal, exact-token terminal writes, project advisory lock, and exact-container effects in migration `0022`; runtime command unit/PostgreSQL tests. |
| `ISS-002-010` | Already remediated | Closed, verified | Production TrustedHost allowlist includes the validated UI and API hosts while rejecting unrelated hosts; `test_production_same_origin_ui_proxy_host_is_allowed`. |
| `ISS-002-011` | Already remediated | Closed, verified | Exported runtime Compose requires the auth-overlay digest and binds allowed origin to public base URL; `test_artifact_compose.py`. |
| `ISS-002-012` | Applicable | Closed, fixed | OpenRouter model catalog requests all output modalities and preserves embedding models; `test_openrouter_provider.py`. |
| `ISS-002-013` | Already remediated | Closed, verified | Canonicalization loads executable payloads only and carries documentation references without reading their bodies; `test_canonicalization_reads.py`. |
| `ISS-002-014` | Already remediated | Closed, verified | Every long-running Compose service has `unless-stopped`; one-shot migration/init jobs remain `no`; `test_compose_recovery_and_isolation_contract`. |
| `ISS-002-015` | Applicable | Closed, fixed | Project-first deployment lock order is shared by request, refresh, rollback, and mutation paths; foundation/runtime-command PostgreSQL serialization tests. |
| `ISS-002-016` | Applicable | Closed, fixed | ASGI multipart capacity guard, 100 MB application limit, 101 MB proxy limit, and 256 MiB API spool tmpfs; `test_request_limits.py` and `test_compose_api_tmpfs_can_spool_the_default_upload_limit`. |
| `ISS-002-017` | Already remediated | Closed, verified | API lifecycle constructs a lazy Milvus client without making API readiness/startup depend on Milvus; lifecycle injection and health tests. |
| `ISS-002-018` | Already remediated | Closed, verified | Shipped runtime and worker identities are fixed at 10001:10001 and runtime-init rejects drift; Compose identity regression plus real Linux runtime acceptance. |
| `ISS-002-019` | Already remediated | Closed, verified | Exclusion inputs use typed string validation and return controlled validation errors for non-strings; `test_exclusion_input_validation.py`. |
| `ISS-002-020` | Applicable | Closed, fixed | Operational setting patches reject null for required persisted fields; settings schema/service and frontend form tests. |
| `ISS-002-021` | Applicable | Closed, fixed | Explicitly cleared optional model settings remain cleared rather than falling back to environment defaults; backend settings and frontend form tests. |
| `ISS-002-022` | Applicable | Closed, fixed | Credential creation normalizes and validates the same transport/header contract consumed by runtime materialization; credential and secret-materializer tests. |
| `ISS-002-023` | Applicable | Closed, fixed | Active exclusions are applied before readiness blocking decisions and compilation uses the same set; operation-exclusion policy and readiness tests. |
| `ISS-002-024` | Applicable | Closed, fixed | Shared deterministic auth-selection engine owns readiness and compilation mapping; credential, readiness, and compiler regressions. |
| `ISS-002-025` | Applicable | Closed, fixed | Shared segment-aware path-template parser supports embedded and multiple placeholders; inventory/compiler and runtime request-builder tests. |
| `ISS-002-026` | Applicable | Closed, fixed | API Inventory schema traversal rewrites references only in schema-keyword positions and preserves literal payload data; inventory parser/contracts tests. |
| `ISS-002-027` | Applicable | Closed, fixed | RFC 6901 traversal resolves object keys and array indices with controlled errors; inventory parser/contracts tests. |
| `ISS-002-028` | Already remediated | Closed, verified | Exact status response definitions cannot fall through to a default media contract; runtime response-contract tests. |
| `ISS-002-029` | Applicable | Closed, fixed | OIDC discovery and cache keys preserve the exact configured issuer, including a trailing slash; runtime OIDC tests. |
| `ISS-002-030` | Applicable | Closed, fixed | DOCX body iteration preserves paragraph/table order and heading context; documentation source-format tests. |
| `ISS-002-031` | Applicable | Closed, fixed | Source snapshot metadata retains warning/info findings while remaining valid and retains blocking-error context while invalid; `test_source_metadata.py`. |
| `ISS-002-032` | Applicable | Closed, fixed | Semantic AI output is validated before success/cache publication and historical invalid success rows are demoted and regenerated; `test_semantic_review.py`. |
| `ISS-002-033` | Applicable | Closed, fixed | Diffs compare effective server URLs/security while excluding unstable provenance-only churn; build pipeline component regressions. |
| `ISS-002-034` | Applicable | Closed, fixed | Parent-first locking and serialized aggregate refresh make concurrent target completion exact; cleanup PostgreSQL concurrency test. |
| `ISS-002-035` | Applicable | Closed, fixed | Cleanup claims one target immediately before work and exact attempt tokens fence leases and terminal writes; cleanup reclaim PostgreSQL test and migration `0024`. |
| `ISS-002-036` | Applicable | Closed, fixed | Retention scheduling isolates per-project failures with bounded retry so due cleanup still runs; cleanup lifecycle integration test. |
| `ISS-002-037` | Applicable | Closed, fixed | Transactional client acquisition, bounded all-resource close, and coordinated dispatcher signaling/cancellation in lifecycle helpers, API, and workers; `test_lifecycle.py`. |
| `ISS-002-038` | Applicable | Closed, fixed | Redis control-plane and RQ clients use explicit connect/operation deadlines bounded by readiness; queue-client and configuration tests. |
| `ISS-002-039` | Applicable | Closed, fixed | Remote fetch owns one total deadline across resolution, redirect/retry, and streamed body work; HTTP-client tests. |
| `ISS-002-040` | Applicable | Closed, fixed | OpenRouter responses are streamed through an enforced byte cap before JSON decode; OpenRouter provider/client tests. |
| `ISS-002-041` | Applicable | Closed, fixed | Password hash/verify work runs off the event loop and last-admin checks retain database serialization; auth timing and user PostgreSQL concurrency tests. |
| `ISS-002-042` | Applicable | Closed, fixed | Users, projects, credentials, tokens, and AI runs return bounded stable pages with totals; frontend consumes all pages where required; management pagination/API/frontend tests and generated OpenAPI. |
| `ISS-002-043` | Applicable | Closed, fixed | Artifact health performs a bounded create, flush, fsync, and delete probe; storage tests. |
| `ISS-002-044` | Applicable | Closed, fixed | Central JSON logging emits allowlisted safe fields, omits raw messages/exceptions, strips query secrets, and cannot serialize arbitrary objects; crypto/redaction and observability tests. |
| `ISS-002-045` | Applicable | Closed, fixed | Versioned key ring decrypts prior versions, encrypts only with the active key, and supplies transactional re-encryption service/CLI; secret rotation and crypto tests. |
| `ISS-002-046` | Applicable | Closed, fixed | Activation proof is immutable after success except for a later equally trusted exact proof; rollback eligibility/runtime command tests. |
| `ISS-002-047` | Applicable | Closed, fixed | CLA workflow reads one configured external commit status/check with read-only permissions and distinguishes policy failure from service unavailability; repository policy test. |
| `ISS-002-048` | Applicable | Closed, fixed | Every structured attempt captures accepted/rejected/transport outcome and aggregates tokens/cost without double counting; OpenRouter and semantic review tests. |
| `ISS-002-049` | Applicable | Closed, fixed | Last-active-admin protection counts active administrators only, so inactive admin records may be demoted; user mutation PostgreSQL tests. |
| `ISS-002-050` | Applicable | Closed, fixed | OAuth expiry rejects booleans, strings, non-finite, zero, and negative values and accepts only finite positive numeric lifetimes; runtime OAuth tests. |
| `ISS-002-051` | Applicable | Closed, fixed | Shared logging allowlist retains safe cleanup/runtime/admission correlation fields with stable JSON types; observability tests. |
| `ISS-002-052` | Already remediated | Closed, verified | No blanket `docs/` ignore remains; repository policy uses `git check-ignore` on a representative authoritative path. |
| `ISS-002-053` | Applicable | Closed, fixed | Deterministic tracked-source manifest writer/checker replaces the stale hand-maintained inventory and is enforced by CI/Make; repository policy test and final clean-tree manifest check. |
| `ISS-002-054` | Already remediated | Closed, verified | `runtime-build` delegates to the canonical Compose `runtime-validator` build and therefore uses the configured image reference; repository policy test and actual image build. |
| `ISS-002-055` | Already remediated | Closed, verified | `.env.example` has one runtime-version assignment and a uniqueness/load regression; `test_example_environment_has_unique_keys_and_loads`. |

## Production-safe migration and compatibility result

The single linear Alembic head advances from `0020` to `0025`:

- `0021` adds explicit current source selection and frozen Build/source binding metadata. Historical
  bindings are marked untrustworthy instead of receiving fabricated provenance. Its downgrade
  refuses to discard an A-B-A selection that the old schema cannot represent.
- `0022` adds runtime-command execution fencing and safely requeues pre-fencing live attempts.
- `0023` adds explicit deployment lifecycle intent and backfills `normal`.
- `0024` adds cleanup-attempt fencing and safely requeues pre-fencing running targets.
- `0025` binds new index generations and Milvus physical rows to the accepted Build execution.

A blank database upgraded through every revision to the unique head and `alembic check` reported no
ORM drift. The legacy-constraint-name upgrade and downgrade/re-upgrade safety scenarios are covered
by `test_schema_drift_postgres.py`.

## Verification record

The final commit was validated with the repository environments and Docker Desktop's Linux engine.
Exact final commands and counts are recorded here after manifest regeneration:

| Boundary | Result |
| --- | --- |
| Backend, contracts, and fixture-server tests | 381 passed, 2 environment-gated skips; all 26 critical coverage floors passed |
| PostgreSQL integration and concurrency | 42 passed within the backend suite |
| Runtime unit/protocol/security | 69 passed |
| Frontend unit/API | 154 passed |
| Frontend lint, strict typecheck, production build | Passed |
| Backend/runtime Ruff, formatting, and strict Pyright | Passed |
| Blank/legacy migration and ORM drift | Passed within the 42 PostgreSQL cases; explicit `alembic check` found no operations |
| Real Linux Docker runtime isolation/replacement/rollback | 1 passed |
| Compose render, images, health, workflow, vector isolation, and browser E2E | 13/13 services valid; 102.398-second workflow passed; real Milvus passed; live Chromium 1 passed; fixture browser matrix 16 passed/8 intentional skips |
| Dependency and secret/repository security scans | Python and pnpm audits found no known vulnerabilities; staged and 38-commit Gitleaks scans found no leaks with the rule/path/shape-scoped fixture allowlist; Trivy HIGH/CRITICAL scan passed |
| Deterministic source manifest and clean-tree checks | Generated from the final tracked-source set, verified before and after commit |

The first host-side Docker test intentionally failed before application execution because Windows
does not provide the configured Unix socket. A second host-side attempt reached the runtime but
correctly failed closed on Windows bind-mount permission semantics. The accepted Docker result was
therefore run inside the Linux backend image with a Docker volume owned by UID/GID 10001, matching
the deployment-worker security boundary; no permission check was disabled.

## External integration boundary

No OpenRouter secret was present or fabricated. Catalog, streaming limit, retry accounting, and
semantic-cache behavior were validated through deterministic HTTP/provider tests against the
documented provider contract. The CLA workflow is repository-complete and fail-closed, but an
operator must install the approved external CLA service and set `CLA_STATUS_CONTEXT` before
accepting external contributions. These are deployment configuration obligations, not unresolved
source findings.
