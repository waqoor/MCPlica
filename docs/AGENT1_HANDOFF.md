# Agent 1 handoff

Agent 1's repository-controlled backend/control-plane and Builder scope is implemented and verified. Detailed traceability is in `docs/evidence/agent1-backend-control-plane.md`.

## Delivered

- Production local authentication, roles/sessions/CSRF/users, projects, immutable sources, encrypted credentials, settings, audit, and related `/api/v1` APIs.
- Bounded SSRF-safe ingestion; OpenAPI 3.0/3.1 and API Inventory normalization; documentation parsing; OpenRouter enrichment; Milvus indexing/retrieval abstractions.
- Immutable RQ Builds, deterministic compiler, shared contracts/generated Schemas, exclusions, 100% expected-coverage gate, validation, artifacts/export, diff, review/rebuild, and conservative semantic reuse.
- Failure-safe queue/cancellation handling, DB integrity/index migration, bounded concurrency/batching, structured correlation logs, readiness, protected metrics, and reproducible Builder/Milvus scale harnesses.

## Verification

- Tests: **76 passed, 1 intentional Docker integration skip**.
- Pyright: **0 errors/warnings**. Ruff: **clean**.
- OpenAPI: official validator passed **49 paths**.
- Alembic: single head `0008`; offline clean upgrade and `0008 -> 0007` downgrade SQL passed.
- Contracts: generated JSON Schemas match their authoritative Pydantic models.
- 1,000-operation local benchmark: **4.652098s median** for parse/compile/validation on Windows 10/Python 3.13.9.

## Migrations

`0001` auth/settings/audit; `0002` projects/sources/credentials; `0003` canonical snapshots; `0004` document index generations; `0005` Builds/AI audit; `0006` validation/exclusions; Agent 2's `0007` deployment/MCP access; `0008` Builder integrity and listing indexes.

## Cross-agent and live-environment dependencies

- Agent 2: run final container protocol/dynamic deployment/runtime hardening acceptance and retain the `0007` contract.
- Agent 3/deployment: supply production API domain/metrics token, provision Prometheus multiprocess storage if needed, apply worker concurrency/retention operationally, and optionally expose Build-history pagination.
- Live PostgreSQL/Redis/Milvus/OpenRouter and Docker were unavailable here. Code/harnesses are present, but those external certifications remain to be run; no credentials or fake success were introduced.
