# Agent 1 backend/control-plane evidence

> Historical workstream snapshot. Verification counts and environment limitations below
> describe that partial stream at handoff time. The reconciled repository-wide result is
> authoritative in `final-integrated-validation.md`.

Date: 2026-08-26

Scope: backend control plane, shared canonical/runtime contracts, secure ingestion, Builder pipeline, validation/export/rebuild behavior, and migrations through `0008`. Dynamic deployment/runtime management and frontend implementation remain the parallel-agent boundaries.

## Requirement trace

| Requirement area | Implemented authority | Focused evidence |
| --- | --- | --- |
| Local auth, roles, sessions, CSRF, users | `backend/app/core/auth.py`, `services/auth.py`, `services/users.py`, `api/auth.py`, `api/users.py` | `test_auth_tokens.py`, full OpenAPI validation |
| Settings, encrypted installation secrets, audit | `services/settings.py`, `services/audit.py`, `repositories/settings.py`, `repositories/audit.py` | `test_settings_service.py`, `test_crypto_redaction.py`, `test_observability.py` |
| Projects, immutable source versions, credentials | `services/projects.py`, `services/sources.py`, `services/credentials.py` and their repositories/APIs | `test_credentials.py`, `test_storage.py`, source/compiler suite |
| SSRF-safe upload/URL ingestion | `clients/http.py`, `core/network_policy.py`, staged artifact storage, structured parser | `test_http_client.py`, `test_network_policy.py`, `test_storage.py` |
| OpenAPI and API Inventory normalization | `parsers/openapi`, `parsers/api_inventory`, `packages/contracts/src/mcp_contracts/{canonical,inventory}.py` | `test_openapi_compiler.py`, `test_inventory_parser.py`, contract tests |
| Documentation parsing/index preparation | `parsers/documentation`, `services/indexing`, bounded async map | `test_documentation.py`, `test_async_utils.py`, `test_vector_store.py` |
| OpenRouter/Milvus boundaries | dedicated clients plus `providers/ai/openrouter.py` and `providers/milvus.py`; no provider SDK calls from routers/services | `test_openrouter_provider.py`, `test_vector_store.py`, live Milvus benchmark harness |
| Immutable Builds/RQ/state machine | `domain/builds.py`, `repositories/builds.py`, `services/builds`, `jobs/build.py`, `clients/build_queue.py` | `test_build_state.py`, build pipeline component tests |
| Compiler, exclusions, coverage, protocol validation | `compilers/mcp/compiler.py`, `validators/build.py`, `services/validation.py`, shared `MCPManifest` | `test_openapi_compiler.py`, `test_build_validation.py`, `test_build_pipeline_components.py` |
| Artifacts and portable export | deterministic ZIP, hashes, no-secret scan, validation report, hardened `compose.example.yaml` in `services/artifacts.py` | `test_build_pipeline_components.py` |
| Diff/review/rebuild/incremental semantics | `services/builds/diff.py`, `services/analysis/reuse.py`, review/rebuild APIs | `test_semantic_reuse.py`, diff component test |
| Operational hardening | production security validation, trusted hosts, JSON correlation logs, bounded readiness, protected Prometheus endpoint | `test_health.py`, `test_observability.py` |
| Scale/optimization | composite listing indexes, DB advisory locks, pooled clients, bounded parsing/embedding/analysis, paged Build history | strict checks plus `backend/benchmarks/builder_scale.py` |
| Generated contract drift | generated manifest/API Inventory JSON Schemas checked against Pydantic authorities | `packages/contracts/tests/test_generated_schemas.py` |

## Migrations

- `0001`: installation users, auth sessions, system settings/secrets, audit.
- `0002`: projects, immutable source versions, encrypted credentials.
- `0003`: immutable canonical snapshots.
- `0004`: rebuildable document-index generation metadata.
- `0005`: Build core, exact source bindings, AI-run audit.
- `0006`: validation reports and persistent operation exclusions.
- `0007`: deployment/MCP-access dependency supplied by Agent 2.
- `0008`: Builder integrity constraints, redundant-index removal, composite listing indexes.

Alembic reports a single `0008 (head)`. Offline PostgreSQL SQL generation passed for a clean `upgrade head` and for `downgrade 0008:0007`. A live PostgreSQL migration was not possible in this session.

## Verification results

- `pytest backend/tests packages/contracts/tests -ra`: **76 passed, 1 skipped in 2.91s**. The skip is the explicitly opt-in Agent 2 Docker runtime acceptance test.
- Strict Pyright over `backend/app`, `backend/tests`, `backend/benchmarks`, and contract sources/tests: **0 errors, 0 warnings**.
- Scoped Ruff over Agent 1 production/tests/migration/benchmarks: **all checks passed**.
- Official `openapi-spec-validator` validation: **passed, 49 paths**.
- Generated contract schema drift/JSON Schema checks: **2 passed**.
- `uv lock --check`: **resolved 102 packages; lock current**.
- `scripts/validate_starter.py`: **32 required files checked; passed**.
- `git diff --check`: **passed**; only Windows LF-to-CRLF notices were emitted.

## Scale baseline

Command:

```powershell
py -3.13 -m uv run --package mcplica-backend python backend/benchmarks/builder_scale.py --operations 1000 --iterations 3
```

On Windows 10 / Python 3.13.9, the median deterministic parse + compile + validation time was **4.652098 seconds**. Samples were 4.638772–4.735398 seconds; parse was 3.357559–3.470160, compile 0.138749–0.146433, validation 0.952589–0.975553. Each manifest contained 1,000 tools and serialized to 856,581 bytes. These are reproducible local observations, not production latency promises.

`backend/benchmarks/milvus_scale.py` provides the live 10,000-chunk, batched, project/generation-scoped upsert/query harness with cleanup. It was not executed because this session had no reachable Milvus service.

## External and cross-agent gates

- Docker was unavailable, so final container protocol validation, runtime hardening inspection, and dynamic-deployment acceptance remain Agent 2/live-environment evidence gates.
- No live PostgreSQL, Redis, Milvus, or OpenRouter credentials/services were supplied. Their integration harnesses and fail-closed abstractions exist, but repository-local tests do not claim live production certification.
- Multi-process Prometheus aggregation requires the deployment layer to create and lifecycle a shared `PROMETHEUS_MULTIPROC_DIR`; production values must supply the API domain and metrics bearer token.
- Deployment/worker configuration must apply the selected Build concurrency and retention policy operationally; those process/scheduler changes are outside Agent 1's deployment ownership.
- The frontend may expose the optional `page`/`page_size` query parameters added to project Build history and should continue consuming the validated OpenAPI contract.
