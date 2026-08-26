# MCPlica

**MCPlica** is an open-source, self-hosted API-to-MCP compiler and deployment platform.

It ingests a company's OpenAPI specification or structured API inventory, optionally incorporates product/API documentation, uses OpenRouter and Milvus only during analysis/build/review, deterministically compiles an MCP-equivalent manifest, validates it, and serves each product through an isolated generic MCP runtime.

> **Starter repository scope:** this repository establishes the production-oriented architecture, executable contracts, core clients, project CRUD foundation, deterministic OpenAPI-to-MCP compiler starter, manifest-driven MCP runtime, Docker/Compose topology, frontend shell, migrations, tests, and governance scaffolding. It is intentionally a starter implementation, not the complete implementation described in `docs/implementation_plan.md`.

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
frontend/            React + Vite + Tailwind + shadcn-style component shell
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

2. Generate a strong encryption key and edit `.env`:

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

5. Start infrastructure and applications:

   ```bash
   make compose-up
   ```

6. Open:

   - MCPlica UI: `http://localhost:8080`
   - Backend OpenAPI: `http://localhost:8000/docs`
   - Backend health: `http://localhost:8000/api/v1/health`
   - Milvus WebUI: `http://localhost:9091/webui/`
   - Traefik dashboard (local only): `http://localhost:8081`

## Local development without full Compose

Start PostgreSQL/Redis/Milvus first, then:

```bash
make backend-dev
make frontend-dev
```

For the runtime, provide a manifest:

```bash
cd mcp_runtime
MCP_MANIFEST_PATH=../tests/fixtures/manifests/petstore.json \
MCP_UPSTREAM_BEARER_TOKEN='replace-me' \
uv run uvicorn app.main:app --host 0.0.0.0 --port 9000
```

The MCP endpoint is `/mcp`; liveness is `/healthz`.

## Starter vertical slice

The starter already includes:

- shared `mcp-manifest/v1` contracts;
- FastAPI application factory and health/readiness endpoints;
- PostgreSQL/Redis/Milvus/OpenRouter/HTTP/Docker/storage clients;
- Project model, repository, service, CRUD API, and Alembic initial migration;
- deterministic OpenAPI parser and compiler starter;
- manifest validator;
- low-level official MCP Python SDK runtime that advertises exact manifest JSON Schemas;
- generic upstream HTTP request builder/executor;
- bearer/API-key/basic upstream authentication from environment secrets;
- static inbound bearer protection for MCP endpoints;
- DNS/host-bound request execution (runtime never accepts arbitrary destination URLs from MCP callers);
- Docker Compose builder topology plus Traefik and Milvus 3.0.0 standalone dependencies;
- React administration shell and Projects screen;
- baseline unit tests and GitHub Actions workflow.

## Authoritative implementation specifications

Read these before expanding the starter:

1. `docs/architecture.md`
2. `docs/design_document.md`
3. `docs/product_requirements.md`
4. `docs/implementation_plan.md`
5. `docs/tech_stack.md`
6. `docs/open_source_and_sponsorship_model.md`

`docs/implementation_plan.md` is the execution order for incremental implementation.

## License and contributions

MCPlica is licensed under **GNU Affero General Public License v3.0 only (`AGPL-3.0-only`)**.

External code contributions require acceptance of the MCPlica Contributor License Agreement. DCO is intentionally not used. See `CLA.md` and `CONTRIBUTING.md`.
