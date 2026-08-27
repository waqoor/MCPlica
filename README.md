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

- Python 3.13
- uv
- Node.js 24 LTS + pnpm
- Docker Engine + Docker Compose v2

## Quick start

1. Copy environment defaults:

   ```bash
   cp .env.example .env
   ```

2. Generate the encryption key and independent auth/pepper/bootstrap secrets, then replace every blank or `REPLACE_...` value in `.env`:

   ```bash
   python scripts/generate_secret_key.py
   ```

3. Install Python projects:

   ```bash
   make install-python
   ```

4. Install frontend dependencies:

   ```bash
   make install-frontend
   ```

5. Start infrastructure/applications. This waits for healthy services, applies
   migrations, and creates the development administrator when it does not exist:

   ```bash
   make compose-up
   ```

6. Sign in with the development defaults:

   - Email: `admin@admin.com`
   - Password: `admin@321`

   - MCPlica UI: `http://localhost:8080`
   - Backend OpenAPI: `http://localhost:8000/docs`
   - Backend health: `http://localhost:8000/api/v1/health`

   PostgreSQL, Redis, Milvus, etcd, and MinIO stay exclusively on the internal
   builder network and are intentionally not published on host ports.

   These well-known credentials are development-only. The seed command refuses
   to run outside `ENV=development`; production installation continues to use the
   prompted bootstrap flow documented in `docs/operations/installation.md`.

## Local development without full Compose

Start PostgreSQL/Redis/Milvus first, then:

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

`docs/implementation_plan.md` is the execution order. `docs/README.md` indexes user, API, operations, security, and release documentation.

## License and contributions

MCPlica is licensed under **GNU Affero General Public License v3.0 only (`AGPL-3.0-only`)**.

External code contributions require acceptance of the MCPlica Contributor License Agreement. DCO is intentionally not used. See `CLA.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, and `GOVERNANCE.md`.
