# Installation and first start

Use the canonical `infra/compose.yaml` topology. Production adds
`infra/compose.production.yaml`; it is an override of the same architecture, not a
second implementation. Run commands from the repository root.

## Prerequisites

Docker Engine and Compose **2.24.4 or newer** are required (`!override` is used for
production listeners). Python 3.13 runs the environment initializer. uv and the
Node.js version in `.node-version` are needed for host development/tests, not for
building/running the application containers. Provision capacity for the configured
Milvus limit (`8g` by default), remaining services, artifacts, and active project
runtimes. Production requires a hardened Linux host and tested backup storage.

Docker Desktop can be used for development. `RUNTIME_HOST_ROOT` must be an absolute
path visible to the Docker daemon, not merely a path visible in a remote client.
The shipped application images require UID/GID 10001. On Linux, `DOCKER_GID` must
match the daemon socket's group; `init_env.py` detects a local socket when available.

## Fresh development installation

```bash
python scripts/init_env.py
docker compose --env-file .env -f infra/compose.yaml config --quiet
docker compose --env-file .env -f infra/compose.yaml up --build --detach --wait --wait-timeout 300
docker compose --env-file .env -f infra/compose.yaml exec -T api python -m app.cli.ensure_development_admin
```

The initializer creates `.env` exclusively with independent random secrets and a
random development administrator password. It refuses to replace existing files;
never regenerate an encryption key for an existing encrypted database. Keep that
key with your encrypted backups, separately from the database, and never commit
`.env`. Read the generated administrator credentials locally, not in shared logs.
The development seed creates only a missing account and never changes its password.

For an existing pre-v1 private environment, do not regenerate secrets. Add
`MCPLICA_VERSION=1.0.0-rc.1`, remove the obsolete operator-set `MCP_RUNTIME_VERSION`, and follow the
release-specific migration guidance before recreating containers.

Set a real `OPENROUTER_API_KEY` and available analysis, validation, and embedding
models for real AI-assisted builds. Missing provider credentials are not silently
replaced with mocks. The control plane can remain usable while build intelligence
is degraded; the acceptance harness supplies explicit test-only HTTP fixtures.

With Make, the equivalent is `make init-env`, `make compose-check`, then
`make compose-up`. No unit/browser/acceptance tests are run by deployment commands.
The reusable runtime image is built by the canonical `runtime-validator` service;
no separately tagged ad hoc runtime build is required.

## Startup and persistence contract

The 13 services are PostgreSQL, Redis, etcd, MinIO, Milvus, migration, API, runtime
validator, builder worker, runtime initializer, deployment worker, frontend, and
Traefik. Eleven are long-running. `migrate` and `runtime-init` must exit **0**, not
remain running. API and both workers wait for successful migration; deployment
also waits for runtime-directory permissions. Builder startup requires healthy
Milvus and runtime validation.

Named volumes retain PostgreSQL, Redis AOF, etcd, MinIO, Milvus, and artifacts.
Runtime manifests/secrets live under the dedicated host bind root. Production
adds persistent ACME storage. `compose down` preserves volumes; **do not use
`down --volumes` on a persistent installation**. Validate backups before upgrades.

PostgreSQL, Redis, etcd, MinIO, and Milvus have no published host ports. API and UI
host ports are loopback-bound. Development Traefik publishes HTTP port 80; do not
expose the development stack to an untrusted network. The public API, builder
worker, and all project runtimes have no Docker socket. Deployment receives the
writable socket; Traefik also reads the socket for routing. Treat socket access as
a privileged host boundary, including a read-only socket mount.

## Verify and operate

```bash
docker compose --env-file .env -f infra/compose.yaml ps --all
curl --fail http://localhost:8000/api/v1/health
curl --fail http://localhost:8000/api/v1/ready
docker compose --env-file .env -f infra/compose.yaml logs --tail=100 api builder-worker deployment-worker
```

Open `http://localhost:8080` and follow `../user-guide.md`. The readiness response
separates core persistence/queue readiness from Milvus/OpenRouter build-time
availability. Investigate unhealthy containers and failed one-shot services before
retrying a build. Secrets must not be copied into diagnostics.

## Production installation

Create a separate fresh environment only for a new installation:

```bash
python scripts/init_env.py --production --output .env.production
```

Set `UI_DOMAIN`, `API_DOMAIN`, `MCP_DOMAIN`, `ACME_EMAIL`, the HTTPS frontend origin,
`MCPLICA_VERSION`, and backend/frontend/runtime **verified release image digests**. Set a dedicated
absolute runtime host directory and real provider credentials. Keep
`DEFAULT_ADMIN_EMAIL` and `DEFAULT_ADMIN_PASSWORD` empty. Follow `domain-tls.md` for
DNS, firewall, certificate, and release verification requirements.

On Linux, select the same absolute file for both Compose interpolation and service
settings:

```bash
export MCPLICA_ENV_FILE="$(pwd)/.env.production"
docker compose --env-file "$MCPLICA_ENV_FILE" -f infra/compose.yaml -f infra/compose.production.yaml config --quiet
docker compose --env-file "$MCPLICA_ENV_FILE" -f infra/compose.yaml -f infra/compose.production.yaml pull
docker compose --env-file "$MCPLICA_ENV_FILE" -f infra/compose.yaml -f infra/compose.production.yaml up --no-build --detach --wait --wait-timeout 300
docker compose --env-file "$MCPLICA_ENV_FILE" -f infra/compose.yaml -f infra/compose.production.yaml exec api python -m app.cli.bootstrap_admin --email admin@example.com --display-name "MCPlica Admin"
```

Bootstrap prompts for the administrator password and one-time bootstrap secret;
neither belongs on the command line. It creates the first user only. Remove
`BOOTSTRAP_SECRET` from the private file after success and recreate API and both
workers with the **same production Compose options**. Do not run the development
seed or destructive acceptance harness against production.

Configuration checks with synthetic domains/digests do not prove image availability,
DNS, ACME issuance, external API behavior, host capacity, or backup restoration.
Complete the live checks in `domain-tls.md` and `../maintainers/release-checklist.md`.

## Host development

`make install-python` installs frozen backend and runtime environments including dev
tools. `make install-frontend` uses the frozen pnpm lockfile. A host backend needs
explicit secured infrastructure endpoints; do not publish internal databases to
make a test pass. Full-stack acceptance instructions are in
`tests/integration/README.md` at the repository root.
