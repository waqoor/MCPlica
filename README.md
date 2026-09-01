# MCPlica

**MCPlica** is an open-source, self-hosted API-to-MCP compiler and deployment platform.

It ingests a company's OpenAPI specification or structured API inventory, optionally incorporates product/API documentation, uses OpenRouter and Milvus only during analysis/build/review, deterministically compiles and validates an MCP manifest, and serves each project through an isolated generic MCP runtime.

> **Release status:** MCPlica is pre-stable. The repository contains the product workspaces, typed control-plane/runtime boundaries, deployment/security controls, CI/release automation, and operator documentation, but a production release still requires the external and live-environment gates in `docs/release/release-checklist.md`.

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
```

## Prerequisites

- Docker Engine and Docker Compose **2.24.4 or newer**.
- Python 3.13 for environment initialization and host-side verification.
- Capacity for the configured Milvus limit (default `8g`), the other services, and each active project runtime.
- uv and Node.js matching `.node-version`, with Corepack/pnpm, only for host development or tests. Docker builds install application dependencies themselves.

## Quick start

Run from the repository root on a fresh local installation:

```bash
python scripts/init_env.py
make compose-check
make compose-up
```

The initializer exclusively creates a private `.env` file with independent random
secrets and a random development administrator password. It refuses to overwrite an
existing environment or rotate its encryption key. Configure `OPENROUTER_API_KEY` and
the build-time model choices before expecting live AI-assisted builds to succeed.

`make compose-up` builds the canonical images, waits for all required services, runs
schema and runtime-directory initialization, and creates the configured development
administrator only when absent. Sign in using `DEFAULT_ADMIN_EMAIL` and
`DEFAULT_ADMIN_PASSWORD` from your private `.env`; do not use the example password as
an installation default. The seed never resets an existing password.

The UI is `http://localhost:8080`, backend OpenAPI is `http://localhost:8000/docs`, and
liveness is `http://localhost:8000/api/v1/health`. PostgreSQL, Redis, Milvus, etcd, and
MinIO have no published host ports. The development Traefik HTTP entrypoint publishes
port 80, so keep this installation on a trusted local host/network.

On systems without Make:

```bash
docker compose --env-file .env -f infra/compose.yaml config --quiet
docker compose --env-file .env -f infra/compose.yaml up --build --detach --wait --wait-timeout 300
docker compose --env-file .env -f infra/compose.yaml exec -T api python -m app.cli.ensure_development_admin
```

Use `make compose-up ENV_FILE=/absolute/path/to/environment` to select another private
environment file consistently for interpolation and service settings. Production
uses the production override, verified release image digests, real domains/TLS, and
interactive first-admin bootstrap; see `docs/operations/installation.md`.

For full-platform verification on a **disposable installation**, follow
`tests/integration/README.md`. Tests are explicit developer/CI commands, never part of
the ordinary deployment startup path. Post-fix evidence and historical limitations
are indexed in `docs/evidence/compose-validation-2026-09-01.md`.

## Local development without full Compose

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

The complete setup, production TLS, configuration, backup, and upgrade procedures are in `docs/operations/`.

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

`docs/implementation_plan.md` is the execution order. `docs/README.md` indexes user, API, operations, security, and release documentation. The evidence-backed second-round disposition of all 48 findings in `issues_001.md` (22 verified, 26 fixed, zero blocked) and the fresh repository/runtime verification snapshot are recorded in `docs/evidence/issues-001-closure.md`.

## License and contributions

MCPlica is licensed under **GNU Affero General Public License v3.0 only (`AGPL-3.0-only`)**.

External code contributions require acceptance of the MCPlica Contributor License Agreement. DCO is intentionally not used. See `CLA.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, and `GOVERNANCE.md`.
