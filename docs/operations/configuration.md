# Configuration reference

The control plane reads unprefixed installation variables such as `DATABASE_URL` and
`OPENROUTER_API_KEY`; a generated MCP runtime reads `MCP_*`. Environment variables and
mounted secret files are deployment inputs, while PostgreSQL remains the authority for
projects, sources, builds, credentials, users, settings, audit records, and deployments.

## Control-plane essentials

| Variable                          | Purpose                                          | Production rule                                                         |
| --------------------------------- | ------------------------------------------------ | ----------------------------------------------------------------------- |
| `ENV`                             | `development`, `test`, or `production`           | Must be `production`                                                    |
| `MCPLICA_VERSION`                 | Compose/package release identity from `VERSION`  | Must equal the deployed release; do not override runtime independently  |
| `API_DOMAIN`                      | Public control-plane API hostname                | Explicit non-local hostname                                             |
| `FRONTEND_ORIGIN`                 | Exact browser origin used by CORS/cookies        | HTTPS origin, no wildcard                                               |
| `METRICS_BEARER_TOKEN`            | Bearer token protecting `/metrics`               | Required; at least 32 characters                                        |
| `DATABASE_URL`                    | SQLAlchemy PostgreSQL URL                        | Dedicated least-privilege database account                              |
| `REDIS_URL`                       | Cache and RQ connection                          | Private network; authentication/TLS when crossing hosts                 |
| `BUILD_QUEUE_NAME`                | Builder-only RQ queue                            | Must differ from the deployment queue                                   |
| `DEPLOYMENT_QUEUE_NAME`           | Docker-authoritative deployment RQ queue         | Must differ from the build queue                                        |
| `SECRET_ENCRYPTION_KEY`           | URL-safe base64 encoded 32-byte AES-256-GCM key  | Required, backed up outside the database                                |
| `SECRET_ENCRYPTION_KEY_VERSION`   | Key identifier stored with ciphertext            | Change only through a planned re-encryption migration                   |
| `SECRET_ENCRYPTION_PREVIOUS_KEYS` | JSON object of prior version to encoded key      | Keep while rows/backups still reference those versions                  |
| `AUTH_SIGNING_KEY`                | Control-plane access-token signing               | Required and distinct from every other key                              |
| `REFRESH_TOKEN_PEPPER`            | Refresh-token verifier pepper                    | Required and distinct                                                   |
| `BOOTSTRAP_SECRET`                | One-time first-admin authorization               | Remove after bootstrap                                                  |
| `DEFAULT_ADMIN_EMAIL`             | Development-only seeded administrator email      | Must be unset in production                                             |
| `DEFAULT_ADMIN_PASSWORD`          | Development-only seeded administrator password   | Must be unset in production                                             |
| `ARTIFACT_ROOT`                   | Immutable source/build artifact storage          | Persistent, access-controlled storage                                   |
| `MCP_RUNTIME_IMAGE`               | Generic runtime image                            | Required as `registry/image@sha256:digest`                              |
| `MCP_RUNTIME_PULL_POLICY`         | `never`, `missing`, or `always` image resolution | Production still requires a digest-pinned reference                     |
| `RUNTIME_HOST_ROOT`               | Docker-daemon-visible per-project runtime files  | Required absolute host path, writable only by deployment-worker UID/GID |
| `RUNTIME_WORKER_ROOT`             | Same bind mounted inside the deployment worker   | Required absolute worker path; defaults to `/runtime-host`              |

Production startup rejects missing encryption/signing/pepper keys, an insecure frontend origin, local API/MCP domains, an absent or short metrics token, TLS-disabled generated routes, mutable runtime image tags, and relative runtime roots.

`DEFAULT_ADMIN_EMAIL` and `DEFAULT_ADMIN_PASSWORD` must be configured together.
In development, `make compose-up` reads them from `.env` to create a missing
administrator, and the live browser/integration harnesses use the same values for
login. `E2E_ADMIN_EMAIL` and `E2E_ADMIN_PASSWORD` can override only the test-harness
login values. The seed is create-only and does not reset an existing account's
password. Both `DEFAULT_ADMIN_*` variables are rejected when `ENV=production`.

## Capacity and bounded work

| Variable                                      |   Default | Valid bound / behavior                                         |
| --------------------------------------------- | --------: | -------------------------------------------------------------- |
| `DATABASE_POOL_SIZE`                          |        10 | 1–100                                                          |
| `DATABASE_MAX_OVERFLOW`                       |        20 | 0–200                                                          |
| `READINESS_TIMEOUT_SECONDS`                   |         5 | >0–30; total bound for concurrent dependency probes            |
| `SHUTDOWN_TIMEOUT_SECONDS`                    |        15 | >0–120 per dispatcher/resource close operation                 |
| `REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS`        |         2 | >0–30; cannot exceed the readiness timeout                     |
| `REDIS_SOCKET_TIMEOUT_SECONDS`                |         4 | >0–30; cannot exceed the readiness timeout                     |
| `BUILD_JOB_TIMEOUT_SECONDS`                   |      3600 | 60–86400                                                       |
| `BUILD_JOB_MAX_ATTEMPTS`                      |         3 | 1–8 total attempts                                             |
| `BUILD_CONCURRENCY`                           |         2 | 1–32                                                           |
| `BUILD_ADMISSION_DISPATCH_INTERVAL_SECONDS`   |         1 | 0.1–60 between PostgreSQL admission scans                      |
| `BUILD_ADMISSION_LEASE_SECONDS`               |       300 | 30–3600; expired admissions are restart-safe                   |
| `BUILD_ADMISSION_HEARTBEAT_SECONDS`           |        30 | 1–300 and strictly shorter than the admission lease            |
| `DEPLOYMENT_JOB_TIMEOUT_SECONDS`              |       900 | 60–7200                                                        |
| `DEPLOYMENT_JOB_MAX_ATTEMPTS`                 |         3 | 1–8                                                            |
| `RUNTIME_COMMAND_DISPATCH_INTERVAL_SECONDS`   |         1 | 0.1–60 between durable command scans                           |
| `RUNTIME_COMMAND_DISPATCH_LEASE_SECONDS`      |        30 | 5–300 for queue-dispatch ownership                             |
| `RUNTIME_COMMAND_EXECUTION_LEASE_SECONDS`     |      1200 | 60–7200 for fenced runtime effects                             |
| `RUNTIME_COMMAND_EXECUTION_HEARTBEAT_SECONDS` |        30 | 1–300; doubled value must be below execution lease             |
| `RUNTIME_ROUTE_RECONCILE_INTERVAL_SECONDS`    |        15 | 5–300 between active edge-route recovery scans                 |
| `CLEANUP_DISPATCH_INTERVAL_SECONDS`           |         5 | 0.1–300; durable cleanup poll interval                         |
| `CLEANUP_LEASE_SECONDS`                       |        60 | 5–3600; expired work is safely reclaimable                     |
| `CLEANUP_MAX_ATTEMPTS`                        |         8 | 1–100 before an operator-visible terminal failure              |
| `CLEANUP_RETENTION_INTERVAL_SECONDS`          |      3600 | 10–86400 between retention scans                               |
| `CLEANUP_ORPHAN_GUARD_DELAY_SECONDS`          |       300 | 5–86400 before an unreferenced upload may be reclaimed         |
| `UPLOAD_MAX_BYTES`                            | 100000000 | 1024–500000000                                                 |
| `MULTIPART_SPOOL_CAPACITY_BYTES`              | 220000000 | At least upload limit plus 1 MiB; provision concurrent uploads |
| `DOCUMENT_MAX_BYTES`                          | 100000000 | 1024–500000000                                                 |
| `FETCH_MAX_BYTES`                             |  25000000 | 1024–500000000                                                 |
| `FETCH_MAX_REDIRECTS`                         |         3 | 0–10, policy checked at every hop                              |
| `FETCH_TIMEOUT_SECONDS`                       |        30 | >0–300 seconds per request phase                               |
| `FETCH_MAX_ATTEMPTS`                          |         3 | 1–8; transient connection, timeout, 429, and 5xx only          |
| `DOCUMENTATION_MAX_CHUNKS_PER_PROJECT`        |     10000 | 1–100000                                                       |
| `DOCUMENT_PARSE_MAX_CONCURRENCY`              |         4 | 1–32 concurrent document parsers per Build                     |
| `EMBEDDING_BATCH_SIZE`                        |        64 | 1–512 texts per provider call                                  |
| `MAX_OPERATIONS_PER_PROJECT`                  |      1000 | 1–100000                                                       |
| `OPENROUTER_MAX_ATTEMPTS`                     |         3 | 1–8 transient transport attempts                               |
| `OPENROUTER_STRUCTURED_MAX_ATTEMPTS`          |         2 | 1–5 schema-conformance attempts                                |
| `OPENROUTER_MAX_CONCURRENCY`                  |         4 | 1–32                                                           |
| `OPENROUTER_MAX_CONTEXT_CHARS`                |    120000 | 1000–1000000                                                   |
| `SEMANTIC_RETRIEVAL_TOP_K`                    |         5 | 1–50 chunks per operation                                      |
| `RUNTIME_MANIFEST_MAX_BYTES`                  |  10000000 | 1024–50000000                                                  |
| `RUNTIME_SECRET_BUNDLE_MAX_BYTES`             |   1000000 | 1024–10000000                                                  |

Size limits are server-side safeguards. Raising a UI limit without changing the server does not increase capacity; raising a server limit requires memory, timeout, abuse, and storage review. Keep the proxy body limit above the application boundary and provision the API `/tmp` tmpfs above `MULTIPART_SPOOL_CAPACITY_BYTES`; the default topology supports two simultaneous maximum-size multipart requests with headroom.

`BUILD_CONCURRENCY` is enforced by PostgreSQL admission leases, not by a process-local
counter. A Build remains `QUEUED` until a lease is committed, and a crashed worker's lease
may be reclaimed only after expiry. Heartbeats, compare-and-set release, FIFO ordering, and
the `/api/v1/build-admission` view make multi-worker behavior observable and restart-safe.
The Build admission token fences every accepted pipeline/result write; cancellation recovery uses
the same lease and never resumes stages. Runtime command dispatch and execution use separate
leases. Each queue delivery carries its execution token, and the deployment worker must renew that
token while holding the PostgreSQL project lock around Docker effects. Increase the execution
lease only for measured slow runtime operations and keep the heartbeat below half the lease.

`RUNTIME_MANIFEST_MAX_BYTES` is frozen into each Build. The Builder measures the exact canonical
manifest serialization and prevents an oversized Build from becoming `READY`; the deployment
preflight and mounted generic runtime enforce the same value or a stricter current value. The
10,000-chunk project limit is an indexing capacity, not permission for 10,000 full-text chunks to
be embedded into a runtime manifest above this byte bound.

## Source and outbound network policy

`ALLOW_HTTP_SOURCE_URLS` is false by default. `SOURCE_ALLOWED_HOSTS` is a comma-separated hostname allowlist for remote source ingestion. `SOURCE_ALLOWED_PRIVATE_CIDRS` is the exceptional private-address allowlist; keep it empty unless an operator has reviewed SSRF reachability.

Runtime upstream access is independently controlled by manifest host evidence plus `RUNTIME_ALLOWED_PRIVATE_HOSTS` and development-only `RUNTIME_ALLOWED_DEVELOPMENT_HOSTS`. Builder allowlists do not grant runtime access. URL userinfo, unsafe schemes, DNS rebinding to denied addresses, and caller-selected destinations remain forbidden.

## Build-time intelligence

`OPENROUTER_BASE_URL` is the HTTP API root used for `/models`,
`/chat/completions`, and `/embeddings`. `OPENROUTER_SITE_URL` has a separate,
optional role: when set, the client sends it as the `HTTP-Referer` attribution
header. It must identify the MCPlica installation or public app, not the OpenRouter
API endpoint; leave it blank when attribution is not wanted. `OPENROUTER_APP_NAME`
is the accompanying attribution label. The remaining settings are
`OPENROUTER_API_KEY`, `..._ANALYSIS_MODEL`, `..._VALIDATION_MODEL`, and
`..._EMBEDDING_MODEL`, plus bounded timeout, retry, concurrency, and context controls.
The API key is builder-only and must never be included in generated runtime
configuration. An administrator may instead save or rotate it through
**Settings > Providers**. That write-only value is encrypted in PostgreSQL, is never
returned to the browser, and takes precedence over `OPENROUTER_API_KEY`; deleting or
revealing it is not exposed as a convenience action. Use **Test connection** for a live
authenticated catalog check, then select all three required model roles in
**Settings > Models**. `MILVUS_URI`, token, and collection configure builder-side
documentation retrieval; Milvus is not a runtime dependency. Compose limits the
standalone Milvus container with `MILVUS_MEMORY_LIMIT` (default `8g`, the documented
standalone minimum); raise it as index volume grows and ensure the Docker host has
at least the configured capacity.

## Health, metrics, and logs

`/api/v1/health` is a liveness probe and reports the running product version.
`/api/v1/ready` concurrently probes PostgreSQL, Redis, artifact storage, the Build queue, Milvus,
and OpenRouter within `READINESS_TIMEOUT_SECONDS`; unavailable core persistence/queue dependencies
return 503, while AI/vector outages are reported as degraded because existing control-plane data
and deployed runtimes remain usable.

Compose health checks cover PostgreSQL, Redis, etcd, MinIO, Milvus, API, both RQ
workers, frontend, and Traefik. Each worker verifies its own hostname/queue registration
through Redis; Traefik uses a private ping entrypoint. `migrate` is a one-shot schema
gate for the API and both workers, while `runtime-init` is the one-shot runtime-directory
gate; both must exit successfully rather than remain running.

`/metrics` exposes bounded-label Prometheus request, Build, stage, generated-operation, OpenRouter usage/cost/rate-limit, and Milvus client metrics. Configure `METRICS_BEARER_TOKEN`; it is mandatory in production. Multi-process API or worker deployments must set `PROMETHEUS_MULTIPROC_DIR` before process start and mount a clean, shared writable metrics directory according to the Prometheus Python client lifecycle. Production logs are structured JSON and include allowlisted request/job/cleanup/runtime correlation identifiers. Raw messages, exception text, query strings, and unknown or sensitive fields are omitted.

## Deployment and routing

`MCP_DOMAIN` is the base for per-project hostnames. `BUILDER_NETWORK`, `EGRESS_NETWORK`, and
`TRAEFIK_NETWORK` name the three existing isolation boundaries; use unique names when intentionally
running a disposable acceptance project beside a retained installation. `TRAEFIK_NETWORK`,
`..._CONTAINER_NAME`, `..._ENTRYPOINT`, `..._TLS`, and `..._CERT_RESOLVER` must match the active
Traefik instance. The shipped backend/runtime images and Compose permissions use fixed UID/GID
10001; `runtime-init` rejects different values instead of advertising unsupported identity
customization. Resource limits default to 512 MiB memory, 1 CPU, 256 PIDs, and 64 MiB tmpfs and may
be tuned only after load and abuse testing. The API and builder worker remain Docker-socket-free.
Only the deployment worker consumes the deployment queue and receives the socket plus runtime-host
mount.

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

Rotate project upstream credentials and MCP access tokens through the API/UI so audit and overlap rules are applied. Upstream secret rotation preserves the credential's source-security binding and can proceed against that stored binding after source drift; changing a scheme/name/location requires a replacement credential and new Build. To rotate the control-plane encryption key, retain a rollback copy, put the old version/key in `SECRET_ENCRYPTION_PREVIOUS_KEYS`, configure a new active version/key, restart, run `python -m app.cli.reencrypt_secrets`, verify every row now references the new version, then remove the old key and restart again. Never change the active key under an existing version. Rotating signing/pepper keys invalidates existing sessions and must be followed by an API restart. Never log old or new values.

## Compose environment resolution

`.env.example` is the canonical key inventory and contains only safe defaults or
blank installation-specific fields. `scripts/init_env.py` copies that complete
shape into a private `.env` and substitutes independently generated secrets and
installation paths. The two files should therefore stay key-for-key aligned, but
must not be byte-for-byte equal: copying private `.env` values into the tracked
template would disclose credentials, while replacing an existing encryption key
would make stored ciphertext unreadable.

`--env-file` selects interpolation inputs; a service-level `env_file` is a separate
Compose input. `scripts/init_env.py` therefore writes `CONTROL_PLANE_ENV_FILE` relative
to `infra/compose.yaml`, and `tests/integration/prepare_compose.py` preserves the same
invariant for custom disposable files. Do not copy or rename an environment file
without regenerating or updating that path. Host-side validation scripts read
`MCPLICA_ENV_FILE`; the Makefile sets it from `ENV_FILE`. Do not print a fully resolved
Compose model into shared logs because it contains secrets. Use `config --quiet` for
routine syntax checks.

`MCPLICA_VERSION` is the only operator-visible Compose release version. Compose maps it to the
backend/runtime compatibility setting and all local image build labels. Environments created
before v1 must add `MCPLICA_VERSION=1.0.0-rc.1` and remove a manually configured
`MCP_RUNTIME_VERSION`; independent values can falsely advertise an incompatible runtime.

The common control-plane environment is shared by migrations, API, builder worker,
and deployment worker. Explicit shell overrides for database URL, queue names,
runtime paths/image, and edge settings are therefore applied consistently.
`RUNTIME_WORKER_ROOT` must match the bind-mount destination; `RUNTIME_HOST_ROOT` is
the corresponding daemon-visible source. Queue names must remain distinct.
`runtime-init` receives only UID, GID, and the worker root, not application secrets.
The production override applies production environment/TLS/domain/origin/image
invariants to all four processes, including migrations.

The canonical bundled topology intentionally fixes Redis/Milvus DNS and artifact
paths to `redis`, `milvus`, and `/data/artifacts`; those are not host-shell service
selection switches. External-service installations require a coherent reviewed
Compose configuration, including worker commands and health checks, rather than
changing only one environment variable.

`tests/integration/production_config_check.py` resolves the production Compose model
using private temporary test configuration and instantiates each process's real
`Settings`. It checks TLS/ports, queue/mount overrides, initializer secret isolation,
and rejection of a missing release image. It neither starts production nor uses
real release-image identifiers. Production requires Compose 2.24.4 or newer and
publishes exactly ports 80 and 443 on Traefik, without retaining development 8443.

## Post-merge configuration corrections (2026-09-01)

`TRAEFIK_NETWORK` now names the Compose edge network and the explicit API/frontend
routing labels as one configuration value. The production provider default uses it
too. Existing dynamically created runtimes still use their own isolated networks;
this does not combine project networks or add a second serving path. Recreate
services deliberately when changing an existing network name.

Canonicalization reads the primary executable source and its executable OpenAPI
dependencies sequentially; documentation contributes immutable metadata there and
is read by the existing indexing boundary instead. This avoids loading all raw
project documentation during configuration discovery/build canonicalization, but
does not establish an unlimited-size or aggregate-memory guarantee.

Documentation and semantic chunk IDs now include project, generation, and source
version identity. The normalized content hashes used for embedding-cache reuse are
unchanged. New generations no longer overwrite other scopes' vector primary keys.
Existing historical indexes are not retroactively rewritten: create a new build
for affected projects from retained sources and verify it before deploying it. Do
not bulk-delete a shared Milvus collection or modify historical build manifests.

Runtime response validation selects the most specific declared status before media
validation. An exact/class response definition with the wrong media type cannot
fall through to `default`. APIs previously accepted through that fallback may now
return an explicit response-contract error; correct the source contract or upstream
response rather than broadening validation to conceal the mismatch.
