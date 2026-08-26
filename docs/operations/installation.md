# Installation and first start

This procedure creates a local, self-hosted MCPlica installation. Production promotion adds the controls in `domain-tls.md` and must use release images rather than local builds.

## Prerequisites

- A Docker Engine host with Compose v2.24 or newer.
- Python 3.13 and uv for host-side development and secret generation.
- Node.js matching `.node-version` with Corepack/pnpm for frontend development.
- At least 8 GiB RAM for the complete local PostgreSQL, Redis, Milvus, API, builder worker, deployment worker, UI, and Traefik topology.

Windows development is supported through Docker Desktop and PowerShell. Production deployment should use a hardened Linux Docker host with persistent storage and a tested backup target.

## Configure the environment

Copy `.env.example` to the ignored `.env` file:

```powershell
Copy-Item .env.example .env
```

Generate the encryption key exactly once:

```powershell
python scripts/generate_secret_key.py
```

Generate independent authentication values:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
python -c "import secrets; print(secrets.token_urlsafe(64))"
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Place the first output in `MCP_LICA_AUTH_SIGNING_KEY`, the second in `MCP_LICA_REFRESH_TOKEN_PEPPER`, and the third temporarily in `MCP_LICA_BOOTSTRAP_SECRET`. Set separate PostgreSQL and MinIO credentials and put the PostgreSQL value into both `MCP_LICA_POSTGRES_PASSWORD` and the password portion of `MCP_LICA_DATABASE_URL`. Never reuse one generated value for another purpose.

Review every setting against `configuration.md`; `.env.example` is a shape, not a production secret store.

## Start and initialize

```powershell
docker build --file infra/docker/runtime.Dockerfile --build-arg RUNTIME_VERSION=1.0.0 --tag mcplica/mcp-runtime:1.0.0 .
docker compose --env-file .env -f infra/compose.yaml up --build --detach --wait --wait-timeout 300
docker compose --env-file .env -f infra/compose.yaml exec api alembic -c ../migrations/alembic.ini upgrade head
docker compose --env-file .env -f infra/compose.yaml exec api python -m app.cli.bootstrap_admin --email admin@example.com --display-name "MCPlica Admin"
```

The bootstrap command prompts for the administrator password and bootstrap secret; neither belongs on the command line. It only creates the first user. Remove `MCP_LICA_BOOTSTRAP_SECRET` from `.env` and recreate the API and both workers after successful bootstrap.

```powershell
docker compose --env-file .env -f infra/compose.yaml up -d --force-recreate api builder-worker deployment-worker
```

## Verify

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health
Invoke-RestMethod http://localhost:8000/api/v1/ready
docker compose --env-file .env -f infra/compose.yaml ps
docker compose --env-file .env -f infra/compose.yaml config --quiet
```

Open `http://localhost:8080`, sign in, and complete the ten-step project workflow in
`../user-guide.md`. Readiness requires PostgreSQL and Redis. Milvus and OpenRouter are
build-time dependencies and appear separately so an operator can distinguish a usable
control plane from degraded build intelligence. PostgreSQL, Redis, Milvus, etcd, and
MinIO remain only on the internal builder network; the base Compose file intentionally
publishes no host ports for them.

The builder worker consumes only `MCP_LICA_BUILD_QUEUE_NAME` and has no Docker socket. The deployment worker consumes only `MCP_LICA_DEPLOYMENT_QUEUE_NAME`; it is the sole application service with the writable Docker boundary and runtime-host mount. Keep those queue names distinct.

## Host development

For a frontend-only code loop, run `make install-frontend` and `make frontend-dev` while
the API remains in Compose. A host-side backend process needs explicitly configured,
secured host-reachable PostgreSQL, Redis, and Milvus endpoints; the base Compose network
does not expose them. For full integration, rebuild/recreate the Compose API and workers.
Do not weaken the internal network or use development settings/anonymous MCP access on
an internet-exposed host.
