# Configuration reference

The control plane reads unprefixed installation variables such as `DATABASE_URL` and
`OPENROUTER_API_KEY`; a generated MCP runtime reads `MCP_*`. Environment variables and
mounted secret files are deployment inputs, while PostgreSQL remains the authority for
projects, sources, builds, credentials, users, settings, audit records, and deployments.

## Control-plane essentials

| Variable                                 | Purpose                                          | Production rule                                                         |
| ---------------------------------------- | ------------------------------------------------ | ----------------------------------------------------------------------- |
| `ENV`                           | `development`, `test`, or `production`           | Must be `production`                                                    |
| `API_DOMAIN`                    | Public control-plane API hostname                | Explicit non-local hostname                                             |
| `FRONTEND_ORIGIN`               | Exact browser origin used by CORS/cookies        | HTTPS origin, no wildcard                                               |
| `METRICS_BEARER_TOKEN`          | Bearer token protecting `/metrics`               | Required; at least 32 characters                                        |
| `DATABASE_URL`                  | SQLAlchemy PostgreSQL URL                        | Dedicated least-privilege database account                              |
| `REDIS_URL`                     | Cache and RQ connection                          | Private network; authentication/TLS when crossing hosts                 |
| `BUILD_QUEUE_NAME`              | Builder-only RQ queue                            | Must differ from the deployment queue                                   |
| `DEPLOYMENT_QUEUE_NAME`         | Docker-authoritative deployment RQ queue         | Must differ from the build queue                                        |
| `SECRET_ENCRYPTION_KEY`         | URL-safe base64 encoded 32-byte AES-256-GCM key  | Required, backed up outside the database                                |
| `SECRET_ENCRYPTION_KEY_VERSION` | Key identifier stored with ciphertext            | Change only through a planned re-encryption migration                   |
| `AUTH_SIGNING_KEY`              | Control-plane access-token signing               | Required and distinct from every other key                              |
| `REFRESH_TOKEN_PEPPER`          | Refresh-token verifier pepper                    | Required and distinct                                                   |
| `BOOTSTRAP_SECRET`              | One-time first-admin authorization               | Remove after bootstrap                                                  |
| `DEFAULT_ADMIN_EMAIL`           | Development-only seeded administrator email      | Must be unset in production                                             |
| `DEFAULT_ADMIN_PASSWORD`        | Development-only seeded administrator password   | Must be unset in production                                             |
| `ARTIFACT_ROOT`                 | Immutable source/build artifact storage          | Persistent, access-controlled storage                                   |
| `MCP_RUNTIME_IMAGE`             | Generic runtime image                            | Required as `registry/image@sha256:digest`                              |
| `MCP_RUNTIME_PULL_POLICY`       | `never`, `missing`, or `always` image resolution | Production still requires a digest-pinned reference                     |
| `RUNTIME_HOST_ROOT`             | Docker-daemon-visible per-project runtime files  | Required absolute host path, writable only by deployment-worker UID/GID |
| `RUNTIME_WORKER_ROOT`           | Same bind mounted inside the deployment worker   | Required absolute worker path; defaults to `/runtime-host`              |

Production startup rejects missing encryption/signing/pepper keys, an insecure frontend origin, local API/MCP domains, an absent or short metrics token, TLS-disabled generated routes, mutable runtime image tags, and relative runtime roots.

`DEFAULT_ADMIN_EMAIL` and `DEFAULT_ADMIN_PASSWORD` must be configured together.
In development, `make compose-up` reads them from `.env` to create a missing
administrator, and the live browser/integration harnesses use the same values for
login. `E2E_ADMIN_EMAIL` and `E2E_ADMIN_PASSWORD` can override only the test-harness
login values. The seed is create-only and does not reset an existing account's
password. Both `DEFAULT_ADMIN_*` variables are rejected when `ENV=production`.

## Capacity and bounded work

| Variable                                        |  Default | Valid bound / behavior                                |
| ----------------------------------------------- | -------: | ----------------------------------------------------- |
| `DATABASE_POOL_SIZE`                   |       10 | 1–100                                                 |
| `DATABASE_MAX_OVERFLOW`                |       20 | 0–200                                                 |
| `READINESS_TIMEOUT_SECONDS`            |        5 | >0–30; total bound for concurrent dependency probes  |
| `BUILD_JOB_TIMEOUT_SECONDS`            |     3600 | 60–86400                                              |
| `BUILD_JOB_MAX_ATTEMPTS`               |        3 | 1–8 total attempts                                    |
| `BUILD_CONCURRENCY`                    |        2 | 1–32                                                  |
| `BUILD_ADMISSION_DISPATCH_INTERVAL_SECONDS` |        1 | 0.1–60 between PostgreSQL admission scans             |
| `BUILD_ADMISSION_LEASE_SECONDS`         |      300 | 30–3600; expired admissions are restart-safe           |
| `BUILD_ADMISSION_HEARTBEAT_SECONDS`     |       30 | 1–300 and strictly shorter than the admission lease    |
| `DEPLOYMENT_JOB_TIMEOUT_SECONDS`       |      900 | 60–7200                                               |
| `DEPLOYMENT_JOB_MAX_ATTEMPTS`          |        3 | 1–8                                                   |
| `CLEANUP_DISPATCH_INTERVAL_SECONDS`     |        5 | 0.1–300; durable cleanup poll interval                |
| `CLEANUP_LEASE_SECONDS`                 |       60 | 5–3600; expired work is safely reclaimable            |
| `CLEANUP_MAX_ATTEMPTS`                  |        8 | 1–100 before an operator-visible terminal failure     |
| `CLEANUP_RETENTION_INTERVAL_SECONDS`    |     3600 | 10–86400 between retention scans                      |
| `CLEANUP_ORPHAN_GUARD_DELAY_SECONDS`    |      300 | 5–86400 before an unreferenced upload may be reclaimed |
| `UPLOAD_MAX_BYTES`                     | 100000000 | 1024–500000000                                       |
| `DOCUMENT_MAX_BYTES`                   | 100000000 | 1024–500000000                                       |
| `FETCH_MAX_BYTES`                      | 25000000 | 1024–500000000                                        |
| `FETCH_MAX_REDIRECTS`                  |        3 | 0–10, policy checked at every hop                     |
| `FETCH_TIMEOUT_SECONDS`                |       30 | >0–300 seconds per request phase                      |
| `FETCH_MAX_ATTEMPTS`                   |        3 | 1–8; transient connection, timeout, 429, and 5xx only |
| `DOCUMENTATION_MAX_CHUNKS_PER_PROJECT` |    10000 | 1–100000                                              |
| `DOCUMENT_PARSE_MAX_CONCURRENCY`       |        4 | 1–32 concurrent document parsers per Build            |
| `EMBEDDING_BATCH_SIZE`                 |       64 | 1–512 texts per provider call                         |
| `MAX_OPERATIONS_PER_PROJECT`           |     1000 | 1–100000                                              |
| `OPENROUTER_MAX_ATTEMPTS`              |        3 | 1–8 transient transport attempts                      |
| `OPENROUTER_STRUCTURED_MAX_ATTEMPTS`   |        2 | 1–5 schema-conformance attempts                       |
| `OPENROUTER_MAX_CONCURRENCY`           |        4 | 1–32                                                  |
| `OPENROUTER_MAX_CONTEXT_CHARS`         |   120000 | 1000–1000000                                          |
| `SEMANTIC_RETRIEVAL_TOP_K`             |        5 | 1–50 chunks per operation                             |
| `RUNTIME_MANIFEST_MAX_BYTES`            | 10000000 | 1024–50000000                                         |
| `RUNTIME_SECRET_BUNDLE_MAX_BYTES`       |  1000000 | 1024–10000000                                         |

Size limits are server-side safeguards. Raising a UI limit without changing the server does not increase capacity; raising a server limit requires memory, timeout, abuse, and storage review.

`BUILD_CONCURRENCY` is enforced by PostgreSQL admission leases, not by a process-local
counter. A Build remains `QUEUED` until a lease is committed, and a crashed worker's lease
may be reclaimed only after expiry. Heartbeats, compare-and-set release, FIFO ordering, and
the `/api/v1/build-admission` view make multi-worker behavior observable and restart-safe.

`RUNTIME_MANIFEST_MAX_BYTES` is frozen into each Build. The Builder measures the exact canonical
manifest serialization and prevents an oversized Build from becoming `READY`; the deployment
preflight and mounted generic runtime enforce the same value or a stricter current value. The
10,000-chunk project limit is an indexing capacity, not permission for 10,000 full-text chunks to
be embedded into a runtime manifest above this byte bound.

## Source and outbound network policy

`ALLOW_HTTP_SOURCE_URLS` is false by default. `SOURCE_ALLOWED_HOSTS` is a comma-separated hostname allowlist for remote source ingestion. `SOURCE_ALLOWED_PRIVATE_CIDRS` is the exceptional private-address allowlist; keep it empty unless an operator has reviewed SSRF reachability.

Runtime upstream access is independently controlled by manifest host evidence plus `RUNTIME_ALLOWED_PRIVATE_HOSTS` and development-only `RUNTIME_ALLOWED_DEVELOPMENT_HOSTS`. Builder allowlists do not grant runtime access. URL userinfo, unsafe schemes, DNS rebinding to denied addresses, and caller-selected destinations remain forbidden.

## Build-time intelligence

OpenRouter settings are `OPENROUTER_API_KEY`, `..._BASE_URL`, `..._ANALYSIS_MODEL`, `..._VALIDATION_MODEL`, and `..._EMBEDDING_MODEL`. The API key is builder-only and must never be included in generated runtime configuration. `MILVUS_URI`, token, and collection configure builder-side documentation retrieval; Milvus is not a runtime dependency. Compose limits the standalone Milvus container with `MILVUS_MEMORY_LIMIT` (default `8g`, the documented standalone minimum); raise it as index volume grows and ensure the Docker host has at least the configured capacity.

## Health, metrics, and logs

`/api/v1/health` is a liveness probe. `/api/v1/ready` concurrently probes PostgreSQL, Redis, artifact storage, the Build queue, Milvus, and OpenRouter within `READINESS_TIMEOUT_SECONDS`; unavailable core persistence/queue dependencies return 503, while AI/vector outages are reported as degraded because existing control-plane data and deployed runtimes remain usable.

Compose health checks cover PostgreSQL, Redis, etcd, MinIO, Milvus, API, both RQ
workers, frontend, and Traefik. Each worker verifies its own hostname/queue registration
through Redis; Traefik uses a private ping entrypoint. `migrate` is a one-shot schema
gate for the API and both workers, while `runtime-init` is the one-shot runtime-directory
gate; both must exit successfully rather than remain running.

`/metrics` exposes bounded-label Prometheus request, Build, stage, generated-operation, OpenRouter usage/cost/rate-limit, and Milvus client metrics. Configure `METRICS_BEARER_TOKEN`; it is mandatory in production. Multi-process API or worker deployments must set `PROMETHEUS_MULTIPROC_DIR` before process start and mount a clean, shared writable metrics directory according to the Prometheus Python client lifecycle. Production logs are structured JSON and include request/job correlation identifiers without secret values.

## Deployment and routing

`MCP_DOMAIN` is the base for per-project hostnames. `TRAEFIK_NETWORK`, `..._CONTAINER_NAME`, `..._ENTRYPOINT`, `..._TLS`, and `..._CERT_RESOLVER` must match the active Traefik instance. Runtime limits default to UID/GID 10001, 512 MiB memory, 1 CPU, 256 PIDs, and 64 MiB tmpfs; tune `RUNTIME_*` only after load and abuse testing. The API and builder worker remain Docker-socket-free. Only the deployment worker consumes the deployment queue and receives the socket plus runtime-host mount.

`BUILDERS_CAN_DEPLOY` defaults false. This is a server authorization policy, not a cosmetic UI toggle. `BUILD_RETENTION_COUNT` keeps at least the newest configured number of Builds per Project plus every active, deployed, or nonterminal Build. `SOURCE_RETENTION_DAYS` removes only versions strictly older than the cutoff, never the latest version of a Source, and never a version referenced by a retained Build. Blank source retention disables source-version expiry.

Project/source deletion and retention commit exact object and vector-generation targets to PostgreSQL before relational references disappear. Cleanup workers lease and retry those targets, check all current database references immediately before external deletion, and expose progress/errors at admin-only `/api/v1/cleanup-jobs`. A referenced content-addressed object is retained and recorded as `skipped_referenced`. Uploads arm a delayed durable orphan guard before staged content is committed, so database persistence failures and process restarts cannot strand a newly created blob. Back up data before enabling retention; cleanup is intentionally destructive after its reference and age/count gates pass.

## Generated runtime settings

The deployment worker supplies a runtime with a read-only manifest and per-project secret bundle. Important settings are:

| Variable                                    | Production invariant                                            |
| ------------------------------------------- | --------------------------------------------------------------- |
| `MCP_ENVIRONMENT`                           | `production`                                                    |
| `MCP_DEPLOYMENT_ID`                         | Exact immutable Deployment identity reported by `/readyz`       |
| `MCP_MANIFEST_PATH` / `MCP_MANIFEST_SHA256` | Mounted file and expected digest must agree                     |
| `MCP_SECRET_BUNDLE_PATH`                    | Mounted only into that project runtime; restrictive permissions |
| `MCP_PUBLIC_BASE_URL`                       | Exact HTTPS origin without credentials, query, or fragment      |
| `MCP_ALLOWED_HOSTS` / `MCP_ALLOWED_ORIGINS` | Explicit project hosts/origins                                  |
| `MCP_TLS_VERIFY`                            | Must remain true                                                |
| `MCP_TRUST_ENVIRONMENT_PROXY`               | Must remain false                                               |
| `MCP_REQUIRE_SECURE_SECRET_PERMISSIONS`     | Keep true                                                       |

Runtime request, response, manifest, secret-bundle, connection-pool, keepalive, and timeout limits are bounded in `mcp_runtime/app/core/config.py`. Build-time MCP inspection separately fails closed at a schema-legal hard ceiling of 100,000 evidence items and 50 MB per response, while honoring any lower configured client limit. Secrets are values inside the mounted bundle, not ad hoc environment variables.

## Secret rotation

Rotate project upstream credentials and MCP access tokens through the API/UI so audit and overlap rules are applied. Upstream secret rotation preserves the credential's source-security binding and can proceed against that stored binding after source drift; changing a scheme/name/location requires a replacement credential and new Build. Rotating the control-plane encryption key requires a tested decrypt/re-encrypt migration and rollback copy; changing it directly makes existing ciphertext unreadable. Rotating signing/pepper keys invalidates existing sessions and must be followed by an API restart. Never log old or new values.
