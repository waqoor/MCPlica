# MCPlica Starter Status

This repository is an implementation-ready starter aligned with the authoritative files in `docs/`. It intentionally implements the foundation and critical contracts rather than pretending the full roadmap is complete.

## Included and working at starter level

- FastAPI control-plane application with liveness/readiness routes and project CRUD foundation.
- SQLAlchemy/Alembic PostgreSQL foundation.
- Redis, Milvus, OpenRouter, Docker, HTTP, storage, database, and MCP coding-client boundaries.
- Provider/repository/service separation.
- Typed canonical API and `mcp-manifest/v1` contracts.
- Deterministic OpenAPI parser/compiler starter.
- Manifest validation starter.
- Generic low-level MCP SDK runtime using Streamable HTTP at `/mcp`.
- Manifest-declared upstream request construction and runtime credential injection.
- React/Vite/Tailwind/shadcn-ready control-plane UI starter.
- Redis/RQ worker foundation.
- Docker Compose foundation with PostgreSQL, Redis, Milvus standalone dependencies, API, worker, frontend, and Traefik.
- AGPL-3.0-only licensing and CLA-only governance scaffolding. DCO is intentionally absent.
- Unit-test starters, fixtures, CI, formatting/lint configuration, and six authoritative project documents.

## Deliberately not claimed complete

The full product roadmap in `docs/implementation_plan.md` is not pre-implemented by this scaffold. In particular, production build orchestration, documentation ingestion/indexing, full AI enrichment, coverage reporting, dynamic runtime deployment, release-grade authentication, complete inventory import, and all hardening phases remain roadmap work.

## Dependency locks

`uv.lock` and `pnpm-lock.yaml` are intentionally not fabricated. The generation environment could not resolve package registries, so dependency manifests are pinned/constrained but transitive lockfiles could not be resolved. In a connected development environment run:

```bash
make lock
```

and commit the resulting lockfiles before the first release.

## CLA gate

`.github/workflows/cla.yml` intentionally fails closed until the GitHub organization-approved CLA verification service is configured. This prevents a placeholder workflow from silently allowing unverified external contributions.
