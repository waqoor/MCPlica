# MCPlica

**MCPlica** is an open-source, self-hosted API-to-MCP compiler and deployment platform.

It ingests a company's OpenAPI specification or structured API inventory, optionally incorporates product/API documentation, uses OpenRouter and Milvus only during analysis/build/review, deterministically compiles and validates an MCP manifest, and serves each project through an isolated generic MCP runtime.

> **Release status:** `1.0.0` is the prepared release candidate; `VERSION` is authoritative. No
> `v1.0.0` tag, GitHub Release, or production image is created until the release-readiness pull
> request is accepted and the external/live gates in the
> [release checklist](docs/release/release-checklist.md) are complete.

## Non-negotiable boundaries

- Self-hosted; no SaaS tenant/subscription/billing model.
- No built-in chat or agent runtime.
- No HITL/approval layer for runtime tool calls.
- OpenRouter is build-time intelligence only.
- Milvus is builder-side semantic infrastructure only.
- PostgreSQL is authoritative state; Redis is cache/queue/temporary state.
- One isolated MCP runtime and subdomain per project.
- MCP runtimes are manifest-driven and reusable; MCPlica does not generate a separate Python application per API.
- Runtime executable mappings are deterministic; AI may enrich semantics but may not invent HTTP behavior.
- External/infrastructure components are accessed through dedicated clients.
- Project and generic runtime code are AGPL-3.0-only; external code contributions require a CLA. DCO is not used.

## Repository layout

```text
backend/             FastAPI builder/control plane
mcp_runtime/         Reusable generic MCP serving runtime
packages/contracts/  Infrastructure-free Pydantic contracts shared by builder/runtime
frontend/            React control plane, typed API clients, unit and browser E2E tests
migrations/          Alembic database migrations
infra/               Docker Compose, Traefik, Milvus, Dockerfiles
scripts/             Developer/bootstrap utilities
tests/               Cross-component fixtures/integration tests
docs/                Authoritative implementation specifications
VERSION              Authoritative product/release version
CHANGELOG.md          Versioned repository change history
```

## Prerequisites

- Docker Engine and Docker Compose **2.24.4 or newer**.
- Python 3.13 for environment initialization and host-side verification.
- Capacity for the configured Milvus limit (default `8g`), the other services, and each active project runtime.
- uv and Node.js matching `.node-version`, with Corepack/pnpm, only for host development or tests. Docker builds install application dependencies themselves.

See the [v1 compatibility matrix](docs/compatibility.md) for supported production/development
platforms, exact toolchain lines, MCP client requirements, and unverified combinations.

## How to run with Docker

Use the existing `infra/compose.yaml` file and the Dockerfiles in `infra/docker/`.
There is no root-level `docker-compose.yml`; include `-f infra/compose.yaml` in the
commands below. Docker must be running, and all commands run from the repository
root. The base configuration is for **local development**, not internet-facing
production. No host-side Node.js, pnpm, or uv installation is needed to run it.

### 1. Get the code and initialize a private environment

For a new checkout:

```bash
git clone https://github.com/yazeedhasan97/MCPlica.git
cd MCPlica
docker version
docker compose version
python scripts/init_env.py
```

Use Python 3.13 (`python3` where that is its executable name). The initializer creates
`.env` with independent random secrets, a random development administrator password,
and an absolute runtime-files path. It refuses to overwrite an existing file.
**For an existing installation, keep its `.env`, encryption key, and data; skip the
initializer.** Keep installation-specific values out of `.env.example`, and never
commit your private `.env`.
An environment created before v1 must add `MCPLICA_VERSION=1.0.0` and remove the obsolete
operator-set `MCP_RUNTIME_VERSION`; follow the release-specific upgrade notes before recreation.

### 2. Configure the installation

Open `.env` in your local editor. The public OpenRouter API root is
`https://openrouter.ai/api/v1`; keep that value in `OPENROUTER_BASE_URL`. Set
`OPENROUTER_API_KEY` and the three model variables there, or sign in as an administrator,
save/rotate the write-only key under **Settings > Providers**, and select the analysis,
validation, and embedding models under **Settings > Models**. A key saved in the UI is
encrypted in PostgreSQL and takes precedence over the environment fallback. OpenRouter is
an external build-time dependency; these commands do not create a local model service or
silently enable provider fixtures. `OPENROUTER_SITE_URL` is optional attribution metadata,
not the OpenRouter API root.

Keep `RUNTIME_UID=10001` and `RUNTIME_GID=10001` for the shipped images. On Linux,
`DOCKER_GID` must match the Docker socket group; the initializer detects a local
socket. `RUNTIME_HOST_ROOT` must be an absolute path visible to the Docker daemon.
Allocate enough memory for Milvus's default `8g` limit plus the other services and
project runtimes. Defaults use UI port 8080, API port 8000, and HTTP edge port 80.

### 3. Build and start the complete platform

```bash
docker compose --env-file .env -f infra/compose.yaml config --quiet
docker compose --env-file .env -f infra/compose.yaml up --build --detach --wait --wait-timeout 300
docker compose --env-file .env -f infra/compose.yaml exec -T api python -m app.cli.ensure_development_admin
```

The startup command builds the backend, frontend, and reusable runtime images and
starts their infrastructure dependencies. Schema migrations and runtime-directory
initialization run automatically before the dependent services. The final command
creates the configured development administrator only when absent; it never resets
an existing password. Tests are **not** run as part of deployment startup.

With Make, `make compose-check` followed by `make compose-up` performs the same
configuration check/startup and administrator initialization after `.env` exists.

### 4. Open the platform and deploy a project runtime

| Purpose                         | Default local address                 |
| ------------------------------- | ------------------------------------- |
| Web application                 | `http://localhost:8080`               |
| Backend API documentation       | `http://localhost:8000/docs`          |
| API liveness                    | `http://localhost:8000/api/v1/health` |
| API readiness/dependency status | `http://localhost:8000/api/v1/ready`  |

Sign in with `DEFAULT_ADMIN_EMAIL` and `DEFAULT_ADMIN_PASSWORD` from your private
`.env`. Complete model configuration, create a project, import its API specification,
configure required upstream credentials, build, configure MCP access, and deploy.
The deployment worker creates the isolated project runtime from the reusable image;
**do not start a second ad hoc runtime or inject its credentials through `docker run`.**
Use the exact project endpoint and authentication details shown in the UI. See the
[user guide](docs/user-guide.md), [API guide](docs/api.md), and
[MCP connection guide](docs/mcp-client-connection.md).

PostgreSQL, Redis, Milvus, etcd, and MinIO have no published host ports. API and UI
host ports are loopback-bound; the development HTTP edge is published, so keep this
stack on a trusted local host/network. Production requires the TLS override below.

### 5. Verify services and inspect logs

```bash
docker compose --env-file .env -f infra/compose.yaml ps --all
curl --fail http://localhost:8000/api/v1/health
curl --fail http://localhost:8000/api/v1/ready
docker compose --env-file .env -f infra/compose.yaml logs --tail=100 api builder-worker deployment-worker
docker compose --env-file .env -f infra/compose.yaml logs --follow --tail=100
```

Expect **11 healthy running services**, plus `migrate` and `runtime-init` exited with
code **0**. Project runtimes are created separately after deployment. Readiness
reports builder-only OpenRouter/Milvus degradation separately from core-service
failure. Therefore the control-plane UI can remain usable while its badge says
**Degraded**; open **Settings > Providers** to distinguish credential configuration,
live provider reachability, and complete model selection. An unhealthy container or
nonzero initializer exit needs investigation;
do not remove health checks or delete volumes to hide it. Review the relevant
service logs without sharing credentials or a fully expanded Compose environment.

### 6. Stop, resume, and apply changes safely

Stop Compose-managed services while retaining their containers and volumes:

```bash
docker compose --env-file .env -f infra/compose.yaml stop
```

Resume, or apply changes to the existing development configuration/source:

```bash
docker compose --env-file .env -f infra/compose.yaml up --build --detach --wait --wait-timeout 300
```

For an unchanged configuration, an individual service can be restarted with:

```bash
docker compose --env-file .env -f infra/compose.yaml restart api
```

Use `up` rather than `restart` to apply `.env` or Compose changes.
`TRAEFIK_NETWORK` selects the shared control-plane edge network; Compose network
creation and API/UI routing labels use that same value. Per-project runtimes keep
their own isolated networks. Do not rename networks on a running installation
without a planned service recreation.

The Docker build context excludes local `.runtime` state, nested private `.env`
files, and private key/certificate files; examples remain available. Keep any
custom runtime host root outside the source checkout. Do not place actual secrets
inside source files, build arguments, or unrecognized directories. Before an upgrade,
back up the database, artifacts, runtime files, and encryption keys and follow the
[upgrade procedure](docs/operations/upgrade.md).

`docker compose --env-file .env -f infra/compose.yaml down` also removes the
Compose-managed containers/networks but keeps named volumes. **Never add `--volumes`
or `-v` unless you explicitly intend to destroy the installation's retained data.**
Project runtimes are managed by the deployment worker, not the Compose service list;
stop them through MCPlica before a complete shutdown/removal. Do not assume `down`
removes project runtimes, and do not delete their host files while they are active.

For another environment filename, use
`make compose-up ENV_FILE=/absolute/path/to/environment`. With direct Compose
commands, pass that file to `--env-file`. Files created by `scripts/init_env.py`
contain the matching service-level `CONTROL_PLANE_ENV_FILE`; host-side validation
scripts additionally read `MCPLICA_ENV_FILE`.

### Production with Docker Compose

Use a hardened Linux host, real UI/API/MCP DNS, and verified immutable release image
digests. For a **new** installation only:

```bash
python scripts/init_env.py --production --output .env.production
```

Edit `.env.production` before continuing: set `UI_DOMAIN`, `API_DOMAIN`, `MCP_DOMAIN`,
`FRONTEND_ORIGIN` to the exact HTTPS UI origin, `ACME_EMAIL`, provider credentials,
and `BACKEND_IMAGE`, `FRONTEND_IMAGE`, `MCP_RUNTIME_IMAGE` to verified
`registry/image@sha256:digest` values. Use a dedicated absolute runtime host path.
Keep both `DEFAULT_ADMIN_*` values empty. No placeholder digest is runnable.

Using a Linux/POSIX shell:

```bash
export MCPLICA_ENV_FILE="$(pwd)/.env.production"
docker compose --env-file "$MCPLICA_ENV_FILE" -f infra/compose.yaml -f infra/compose.production.yaml config --quiet
docker compose --env-file "$MCPLICA_ENV_FILE" -f infra/compose.yaml -f infra/compose.production.yaml pull
docker compose --env-file "$MCPLICA_ENV_FILE" -f infra/compose.yaml -f infra/compose.production.yaml up --no-build --detach --wait --wait-timeout 300
docker compose --env-file "$MCPLICA_ENV_FILE" -f infra/compose.yaml -f infra/compose.production.yaml exec api python -m app.cli.bootstrap_admin --email admin@example.com --display-name "MCPlica Admin"
```

Replace the example administrator email/name with your own. Bootstrap prompts for
its one-time secret and the new password; do not put passwords on the command line.
Remove `BOOTSTRAP_SECRET` after success and recreate the API and workers using the
same production Compose options. Production publishes edge ports 80/443, persists
ACME state, and does not locally build release images. Use both Compose files for
subsequent status, logs, restart, and shutdown operations.

Read the [installation](docs/operations/installation.md),
[Docker Compose](docs/operations/docker-compose.md),
[TLS/DNS](docs/operations/domain-tls.md), and
[backup/restore](docs/operations/backup-restore.md) instructions before production
use. Configuration validation is not proof of public DNS, certificate issuance,
release-image availability, provider behavior, or backup restoration.

### Optional end-to-end validation

Follow [cross-service acceptance](tests/integration/README.md) on a **disposable
installation only**. The harness deliberately stops/recreates services and changes
project settings; it must not run against production or retained business data.
Normal Docker startup never invokes it. Commit-specific validation results and limitations are in
the [v1.0.0 release-candidate evidence](docs/evidence/v1.0.0-release-candidate.md).

For the post-merge regression scope and remaining limitations, see
[post-merge validation](docs/evidence/post-merge-validation-2026-09-01.md).

## Local development without full Compose

The Make targets use the same absolute backend/runtime virtual-environment paths
for installation and execution, with frozen dependency resolution.

Install development dependencies with `make install-python` and
`make install-frontend`. A host-side backend also requires explicitly configured,
secured host-reachable PostgreSQL/Redis/Milvus endpoints; the base Compose file does
not expose those services. Then:

```bash
make backend-dev
make frontend-dev
```

The generic runtime is launched through the deployment worker so it receives a verified manifest digest and project-scoped read-only secret bundle. Exercise it in isolation through its security/protocol tests:

```bash
cd mcp_runtime
uv run pytest tests/test_manifest_security.py tests/test_protocol_and_auth.py
```

Deployed runtime liveness is `/healthz`, readiness is `/readyz`, and MCP Streamable HTTP is `/mcp`. Do not inject ad hoc credential environment variables in place of the canonical secret bundle.

The complete setup, production TLS, configuration, Compose, troubleshooting, backup, and upgrade
procedures are in `docs/operations/`.

## Implemented product surface

The canonical implementation includes:

- shared `mcp-manifest/v1` contracts;
- FastAPI application factory and health/readiness endpoints;
- PostgreSQL/Redis/Milvus/OpenRouter/HTTP/Docker/storage clients;
- cookie/CSRF authentication, local admin/builder roles, settings, audit and encrypted credential boundaries;
- projects, immutable sources/versions, parsing/indexing, canonical build evidence, validation and deployment lifecycle;
- deterministic OpenAPI/inventory compilers with explicit provenance and manifest validation;
- low-level official MCP Python SDK runtime that advertises exact manifest JSON Schemas;
- generic upstream HTTP request builder/executor;
- project-scoped upstream and inbound MCP authentication from mounted secret bundles;
- static inbound bearer protection for MCP endpoints;
- DNS/host-bound request execution (runtime never accepts arbitrary destination URLs from MCP callers);
- hardened Docker/Compose topology plus a fail-closed production TLS override;
- responsive ten-step React workflow and project/global operational workspaces;
- frontend unit and Chromium/Firefox/WebKit/mobile E2E journeys;
- CI, dependency/secret/image scans, SBOM/checksum generation, and signed digest release automation.

## Authoritative implementation specifications

Read these before changing product behavior:

1. `docs/architecture.md`
2. `docs/design_document.md`
3. `docs/product_requirements.md`
4. `docs/implementation_plan.md`
5. `docs/tech_stack.md`
6. `docs/open_source_and_sponsorship_model.md`

`docs/implementation_plan.md` is the execution order. `docs/README.md` indexes user, API,
operations, security, and release documentation. The historical second-round disposition of 48
findings from the unshipped `issues_001.md` source register is retained in
`docs/evidence/issues-001-closure.md`; it is not independently reconstructible from this checkout.
The verified disposition of all 55 tracked `issues_002.md` findings (12 retained fixes, 43
implemented fixes, zero open) is recorded in `docs/evidence/issues-002-closure.md`, with focused
foundation proof for `ISS-002-002` through `ISS-002-009` in
`docs/evidence/issues-002-foundation-closure.md`.

Release users should start with the [v1.0.0 notes](docs/releases/v1.0.0.md),
[changelog](CHANGELOG.md), [compatibility matrix](docs/compatibility.md), and
[release process](docs/release/release-process.md). Historical audit ledgers remain evidence for
their stated snapshots; they are not proof of the current release candidate by themselves.

## License and contributions

MCPlica is licensed under **GNU Affero General Public License v3.0 only (`AGPL-3.0-only`)**.

External code contributions require acceptance of the MCPlica Contributor License Agreement. DCO
is intentionally not used. See [CONTRIBUTING.md](CONTRIBUTING.md),
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), [GOVERNANCE.md](GOVERNANCE.md), and
[SUPPORT.md](SUPPORT.md).
