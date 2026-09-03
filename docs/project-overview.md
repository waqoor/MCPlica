# Project overview

MCPlica is a self-hosted compiler and deployment platform for turning API descriptions into
isolated MCP servers. This document records the stable product boundaries, the implemented
surface, the implementation sources of truth, and the repository map.

## Non-negotiable boundaries

- MCPlica is self-hosted; it has no SaaS tenant, subscription, or billing model.
- It does not provide a built-in chat or agent runtime.
- It does not add a human-approval layer to runtime tool calls.
- OpenRouter is used for build-time intelligence only.
- Milvus is builder-side semantic infrastructure only.
- PostgreSQL is authoritative state; Redis holds cache, queue, and temporary state.
- Each project has one isolated MCP runtime and subdomain.
- MCP runtimes are manifest-driven and reusable; MCPlica does not generate a separate Python
  application for each imported API.
- Runtime executable mappings are deterministic. AI may enrich semantics but may not invent HTTP
  behavior.
- External and infrastructure components are accessed through dedicated clients.
- Project and generic-runtime code is AGPL-3.0-only. External code contributions require a CLA;
  DCO is not used.

## Implemented product surface

The canonical implementation includes:

- shared `mcp-manifest/v1` contracts;
- a FastAPI control plane with health and readiness endpoints;
- PostgreSQL, Redis, Milvus, OpenRouter, HTTP, Docker, and storage clients;
- cookie/CSRF authentication, local admin and builder roles, settings, audit, and encrypted
  credential boundaries;
- projects, immutable sources and versions, parsing, indexing, canonical build evidence,
  validation, and deployment lifecycle management;
- deterministic OpenAPI and inventory compilers with explicit provenance and manifest validation;
- a reusable runtime based on the official MCP Python SDK that advertises exact manifest JSON
  Schemas;
- bounded upstream HTTP request construction and execution;
- project-scoped upstream and inbound MCP authentication from mounted secret bundles;
- static inbound bearer protection for MCP endpoints;
- DNS- and host-bound execution, so callers cannot supply arbitrary runtime destinations;
- hardened Docker Compose topology with a fail-closed production TLS override;
- a responsive ten-step React workflow plus project and global operational workspaces;
- frontend unit tests and Chromium, Firefox, WebKit, and mobile browser journeys; and
- CI, dependency, secret, and image scans, with SBOM, checksum, signed-digest, and provenance-aware
  release automation.

## Authoritative implementation specifications

Read these documents before changing product behavior. A later explicit decision overrides an
earlier conflict:

1. [Architecture](architecture.md)
2. [Design document](design_document.md)
3. [Product requirements](product_requirements.md)
4. [Implementation plan](implementation_plan.md)
5. [Technology stack](tech_stack.md)
6. [Open-source and sponsorship model](open_source_and_sponsorship_model.md)

The implementation plan defines execution order. The [documentation index](README.md) links the
user, API, operations, security, and maintainer material.

## Repository layout

```text
backend/             FastAPI builder and control plane
mcp_runtime/         Reusable generic MCP serving runtime
packages/contracts/  Infrastructure-free contracts shared by builder and runtime
frontend/            React control plane, typed API clients, and browser tests
migrations/          Alembic database migrations
infra/               Docker Compose, Traefik, Milvus, and Dockerfiles
scripts/             Developer, validation, and bootstrap utilities
tests/               Cross-component fixtures and integration tests
docs/                Product, development, operations, and security documentation
VERSION              Authoritative product and release version
CHANGELOG.md          Versioned repository change history
```
