# MCPlica Technology Stack and Engineering Standards

**Status:** Authoritative technology/engineering specification  
**Date:** 2026-08-24

## 1. Document ownership

This document owns **technology choices and engineering standards**: languages, frameworks, libraries, databases, infrastructure, package/dependency rules, testing/tooling, deployment technology, version policy, coding standards, and rationale for major choices.

It does not redefine product scope (`product_requirements.md`), system boundaries (`architecture.md`), technical contracts (`design_document.md`), phase order (`implementation_plan.md`), or open-source governance (`open_source_and_sponsorship_model.md`).

---

## 2. Version policy

### 2.1 General rule

All production dependencies must be **explicitly pinned through lockfiles/container image tags or digests**. Do not deploy floating `latest` tags.

Root `VERSION` is authoritative for the product/package/API/frontend/runtime/image release. Literal
copies required by package managers and generated artifacts are synchronized by
`scripts/release_version.py` and checked in CI. Protocol/schema/prompt versions remain independent
and change only with their contracts.

The versions below define the approved major/minor baseline as of this specification date. During the initial implementation, use the newest stable/security-patched release within the approved line unless a documented compatibility issue requires the immediately preceding supported release.

Patch/minor security upgrades that do not change the architecture may be accepted through normal dependency maintenance and lockfile updates. Major-version upgrades require compatibility tests and an update to this document when they materially affect contracts.

### 2.2 Baseline versions

| Area              | Baseline                                                               |
| ----------------- | ---------------------------------------------------------------------- |
| Python            | 3.13.x                                                                 |
| Node.js           | 24 LTS                                                                 |
| React             | 19.2.x                                                                 |
| Vite              | 8.2.x supported line                                                   |
| Tailwind CSS      | 4.3.x                                                                  |
| PostgreSQL        | 18.x; current maintenance baseline at spec date 18.6                   |
| Redis Open Source | 8.x; use current supported security-patched release                    |
| Milvus            | 3.x standalone line; use current stable Docker Compose release         |
| MCP Python SDK    | v2 stable line; lock 2.1.1 and validate protocol revision `2026-07-28` |
| Traefik           | v3 stable line                                                         |

Do not use beta/RC/development releases for production base services.

---

## 3. Primary language/runtime choices

### Backend and MCP runtime — Python 3.13

Python is authoritative for:

- FastAPI control-plane backend;
- background jobs;
- parsing/normalization;
- AI/OpenRouter integration;
- Milvus integration;
- deterministic compiler/validators;
- Docker runtime management;
- generic MCP runtime.

Rationale:

- direct fit with FastAPI/Pydantic;
- official MCP Python SDK;
- strong JSON/schema/OpenAPI ecosystem;
- consistent code sharing/typing between compiler and runtime contracts;
- simple self-hosted deployment.

### Frontend — TypeScript

TypeScript is mandatory; no JavaScript-only application modules except unavoidable tool configuration.

Rationale: API/schema-heavy admin application benefits from strict contracts and generated/validated types.

---

## 4. Backend framework stack

### FastAPI

Use FastAPI as the versioned control-plane REST/API framework.

Responsibilities:

- request routing;
- OpenAPI exposure for the control plane;
- validation integration;
- auth middleware/dependencies;
- SSE endpoints;
- health/readiness.

Do not use FastAPI as an excuse to place domain logic inside route functions.

### Uvicorn

Use Uvicorn as the ASGI server inside backend/runtime containers. Production process count is configured by deployment resources; do not embed Gunicorn unless operational evidence requires it.

### Pydantic v2 + Pydantic Settings

Pydantic is authoritative for:

- REST DTOs;
- configuration;
- canonical API models;
- AI structured results;
- MCP manifest models;
- runtime config;
- typed value validation.

Do not use Pydantic v1 compatibility mode.

### SQLAlchemy 2.x

Use SQLAlchemy 2.x async APIs and explicit repository boundaries.

Approved PostgreSQL URL/driver style:

```text
postgresql+psycopg://...
```

using psycopg v3 async support.

Do not use Django ORM, Tortoise, or raw psycopg query code for normal domain persistence.

### Alembic

All relational schema changes use Alembic. No production `create_all()` migration mechanism.

---

## 5. Relational database

### PostgreSQL 18

PostgreSQL is the sole authoritative relational/domain datastore.

Use for:

- users/sessions;
- projects/sources/builds;
- deployment state;
- encrypted credential records;
- validation/audit state;
- system settings;
- serialized JSONB canonical/report data where appropriate.

Approved features:

- UUID;
- JSONB;
- CITEXT extension for user emails if available/installed by migration;
- advisory locks where useful;
- standard indexes/partial indexes;
- check constraints/unique constraints.

Do **not** install/use pgvector for this project.

### PostgreSQL engineering rules

- transactions explicit at service/use-case boundary;
- N+1 queries measured/prevented;
- indexes created for actual query patterns;
- JSONB is appropriate for versioned schema documents, not a replacement for all relational design;
- connection pool bounds configurable;
- migrations reversible where practical;
- backup/restore documented.

---

## 6. Cache and background queue

### Redis Open Source 8.x

Redis is non-authoritative.

Approved purposes:

- RQ queue backend;
- short-lived caching;
- build/deployment progress events;
- idempotency/temporary coordination;
- bounded locks where durable correctness is also protected elsewhere;
- model catalog cache.

No project/build authoritative truth may exist only in Redis.
Every Redis/RQ client configures bounded socket connect and operation timeouts; blocking queue
operations must not outlive shutdown/readiness indefinitely.

### RQ

Use RQ as the initial Redis-backed job executor.

Job categories:

- build;
- indexing;
- OpenRouter analysis;
- validation/packaging;
- deployment/runtime management;
- source URL refresh.

Rules:

- job payload contains IDs, not large source blobs/secrets;
- worker reloads authoritative rows from PostgreSQL;
- every job updates durable status;
- transient retries bounded;
- one job function is an orchestration boundary, not a place for low-level SDK access;
- async service code may be executed from worker entrypoints through one controlled event-loop wrapper.

Do not introduce Celery/RabbitMQ/Kafka unless future measured requirements justify replacing RQ and the documentation is updated.

---

## 7. Vector database

### Milvus 3.x

Milvus is mandatory for semantic/vector retrieval.

Use standalone Docker Compose topology for the initial self-hosted product, including the officially required support services for the pinned Milvus release.

Use via:

- `pymilvus` inside `MilvusClient` only;
- `MilvusVectorStore` provider for domain semantics.

Use cases:

- documentation chunk embeddings;
- source-description semantic retrieval;
- operation-document correlation;
- RAG context for build-time OpenRouter analysis.

Do not use:

- pgvector;
- Pinecone;
- Qdrant;
- Weaviate;
- Elasticsearch vector search

as parallel implementations.

Milvus is rebuildable and not a source of project truth.

---

## 8. AI provider

### OpenRouter

OpenRouter is the only AI provider integration required for the initial platform.

Use it for:

- structured semantic analysis;
- description/title enrichment;
- semantic validation/review;
- embeddings for Milvus indexing;
- live model/capability catalog.

Do not use OpenRouter for:

- generated MCP runtime execution;
- runtime routing decisions;
- end-user chat;
- autonomous business API calls.

### OpenRouter client/provider standard

`OpenRouterClient` owns:

- base URL;
- bearer authentication;
- request serialization;
- endpoint calls;
- timeouts/retry-aware errors;
- raw response normalization.
- response streaming with endpoint-specific byte ceilings before JSON buffering.

`OpenRouterProvider` owns:

- selected model IDs;
- structured output contract;
- embeddings interface;
- capability/model catalog semantics;
- usage/cost normalization.
- per-structured-attempt accepted/rejected/transport outcome accounting.

Services never call OpenRouter HTTP endpoints directly.

### Structured outputs

Use OpenRouter JSON-Schema structured outputs when supported by the selected model. Always validate returned data with Pydantic after transport validation and before publishing a successful reusable AI-run record.

Do not rely on “valid-looking JSON” alone.

### Embeddings

Use the OpenRouter embeddings API so model sourcing remains under the same configured provider surface. Record embedding model and dimensions with each Milvus index generation.

---

## 9. HTTP client

### httpx

Use `httpx.AsyncClient` as the common Python HTTP foundation.

All raw HTTP access goes through project clients:

- builder `HttpClient` for secure source/document fetching and as the underlying transport used by `OpenRouterClient`;
- runtime `ApiClient` for product API execution.

Engineering rules:

- reuse pools;
- explicit connect/read/write/pool timeouts;
- one caller-owned total deadline for multi-step fetches (DNS/policy, redirects, retries, and body);
- explicit redirect policy;
- bounded streaming for downloads/responses;
- TLS verification on by default;
- no secret headers in logs;
- predictable proxy/environment behavior;
- normalize errors before crossing client boundary.

Do not use `requests` in asynchronous application/runtime paths.

---

## 10. OpenAPI and schema processing

Approved libraries:

- `openapi-spec-validator` for specification validation where compatible;
- `jsonschema` for JSON Schema validation;
- `referencing` for standards-based reference handling primitives;
- `PyYAML` using safe loading only;
- standard library `json` or `orjson` for bounded serialization paths.

The project must still own its normalization/compiler logic; do not let a third-party converter become the canonical domain model.

### JSON/YAML rules

- safe YAML loader only;
- reject Python/object tags;
- size/depth/reference recursion limits;
- canonical serialization/hashing controlled by project code.

---

## 11. Documentation processing

Approved libraries:

- `PyMuPDF` for text extraction from PDFs;
- `openpyxl` in read-only mode for bounded XLSX text extraction;
- `python-docx` for bounded DOCX paragraph/table text extraction;
- `markdown-it-py` for Markdown parsing/structure if needed;
- `beautifulsoup4` for bounded HTML text/section extraction;
- standard library HTML utilities as appropriate.

Rules:

- no OCR dependency in core V1;
- Office Open XML archives must be inspected for unsafe paths, encryption, macros,
  entry count, expanded size, and compression ratio before parsing;
- spreadsheet formulas and document code are data only and are never executed;
- no browser engine required for ordinary documentation crawling;
- do not execute page JavaScript;
- do not preserve/render arbitrary source HTML unsanitized;
- preserve provenance and headings.

Frontend rendering of Markdown/derived documentation should use a renderer that escapes raw HTML by default; if HTML rendering is enabled, use `rehype-sanitize` or equivalent explicit sanitization.

---

## 12. Cryptography/authentication libraries

Approved:

- `cryptography` for AES-256-GCM secret envelopes;
- `pwdlib[argon2]` (or direct Argon2 library if compatibility requires) for user password hashing;
- `PyJWT` for signed short-lived access tokens if JWT is retained by implementation;
- `secrets` standard library for high-entropy opaque tokens;
- `hashlib`/HMAC for token verifiers/content hashes as designed.

Do not implement custom cryptographic primitives.

Secrets must use dedicated redaction types/filters.

---

## 13. MCP technology

### Official Model Context Protocol Python SDK v2

Use the official `modelcontextprotocol/python-sdk` v2 stable line.

Approved transport:

- Streamable HTTP for deployed runtime `/mcp`.

Use the exact-schema capable low-level server API (or equivalent v2 SDK API that publishes provided JSON Schema unchanged) for generated tools.

Reason:

- tool definitions are dynamic/generated from manifests;
- schemas must not be inferred from handwritten decorators/functions;
- runtime needs exact control over structured results/errors.

### MCP validation

Use:

- official Python MCP client in backend integration tests/validator client;
- MCP Inspector as a developer/manual interoperability tool;
- automated protocol tests against the runtime container.

Automated inspection must remain bounded without undercutting the supported schema: the validator
client hard ceiling is 100,000 evidence items and 50 MB per response, and any lower configured
limit is enforced after typed validator evidence is parsed.

Do not build a proprietary MCP protocol implementation when the official SDK supports the needed behavior.

---

## 14. Shared protocol-contract package

Create one infrastructure-free Python workspace package at `packages/contracts/` containing the authoritative versioned Pydantic/JSON Schema contracts that must be identical in builder and runtime, especially `mcp-manifest/v1`.

Rules:

- package contains models/schemas only, no database/client/provider/service imports;
- backend compiler depends on it;
- generic runtime depends on it;
- one schema/version implementation prevents drift;
- changes require compiler/runtime compatibility tests.

## 15. Generic runtime stack

Runtime dependencies shall be deliberately smaller than builder dependencies.

Required runtime packages only:

- Python 3.13;
- official MCP Python SDK v2;
- Pydantic v2;
- httpx;
- minimal ASGI/Uvicorn dependencies;
- cryptographic/JWT/JWKS dependencies only if required for inbound auth;
- structured logging library.

Forbidden runtime dependencies:

- OpenRouter SDK/client;
- `pymilvus`;
- SQLAlchemy/PostgreSQL driver;
- Redis/RQ;
- Docker SDK;
- frontend/browser tooling;
- PDF/OpenAPI build parsers unless directly needed to validate manifest schema (normally not).

This dependency separation must be asserted in CI.

---

## 16. Docker management

### Docker Engine + Docker Compose

Docker Compose is the base installation/development orchestration mechanism.

Use Docker Engine API for dynamic project runtime creation through the Python `docker` SDK inside `DockerClient`.

The Docker SDK is permitted only in the deployment integration layer/worker.

### Runtime Docker image

Use multi-stage build and an official slim Python base. Pin the base tag/digest in release builds.

Requirements:

- non-root user;
- minimal packages;
- no compilers/build caches in final image;
- read-only filesystem compatible;
- healthcheck;
- OCI metadata labels;
- reproducible dependency install from lockfile.

### Docker socket

Do not mount `/var/run/docker.sock` into the public FastAPI API container or runtime containers.

The deployment worker is the only intended Docker-authoritative service. Production documentation should recommend a constrained socket proxy or equivalent when practical.

---

## 17. Reverse proxy/routing

### Traefik v3

Traefik is authoritative for edge routing.

Use Docker provider with:

- `exposedByDefault=false`;
- explicit per-runtime labels;
- TLS/HTTPS in production;
- explicit service port;
- secrets excluded from labels.

Rationale: dynamic Docker container discovery and hostname rules fit the one-subdomain-per-project requirement without maintaining manual proxy configuration files per build.

Do not add Nginx/Caddy as a parallel required proxy path.

---

## 18. Frontend stack

### React 19.2

Use functional components/hooks and TypeScript.

### Vite 8.2

Use Vite for development/build. This product needs an authenticated SPA/admin interface, not SSR/SEO rendering.

Do not introduce Next.js unless product scope changes to require SSR/public content application behavior.

### Tailwind CSS 4.3

Tailwind is the styling system.

Use CSS-first configuration appropriate to Tailwind 4; avoid legacy Tailwind 3 configuration patterns unless required by a dependency.

### shadcn/ui

Use shadcn/ui components copied into the repository as the accessible component foundation. Treat generated components as project-owned source and adapt them consistently rather than adding another full UI framework.

### React Router

Use React Router for SPA routing.

### TanStack Query

Use for server state:

- API fetch/cache;
- invalidation;
- polling fallback;
- mutations.

Do not store server resources in a global client state library unnecessarily.

### React Hook Form + Zod

Use for complex forms and client-side validation. Backend Pydantic remains authoritative; frontend validation is UX, not security.

### Additional approved UI utilities

- Lucide for icons;
- Sonner or shadcn-compatible toast implementation for transient notifications;
- `react-markdown` + sanitization for safe Markdown display when needed.

Do not add Material UI/Ant Design/Chakra as parallel component frameworks.

---

## 19. Frontend/backend API contract

The FastAPI `/api/v1` OpenAPI schema is the authoritative transport contract.

Implemented contract pipeline:

- `backend/generate_openapi.py` renders the deterministic tracked `openapi.json` from the live FastAPI application;
- `frontend/src/api/generated/schema.d.ts` contains immutable TypeScript aliases generated by `openapi-typescript`;
- `frontend/src/api/generated/zod.ts` contains strict success-response validators generated from the same artifact;
- the existing cookie/CSRF/refresh-aware fetch client requires an endpoint validator for every JSON response; a malformed successful response fails with `RESPONSE_CONTRACT_INVALID`, the endpoint, safe field-level issues, and the backend request ID;
- `make api-contract` regenerates all artifacts and `make api-contract-check` fails on backend or frontend drift.

Do not manually duplicate dozens of DTO interfaces if reliable generation can eliminate drift.

Generated frontend API code belongs under `frontend/src/api/generated/` and must not contain business logic.
Presentation enrichment (for example project or actor names joined by the UI) must remain an explicit view model or batch join and must never be added as a phantom transport field.

---

## 20. Logging/observability

### Python logging

Use `structlog` over standard logging integration for structured JSON production logs.

Requirements:

- allowlisted request/job/project/build/deployment/cleanup/runtime-command IDs;
- development pretty output allowed;
- central redaction and JSON-safe normalization;
- production exception diagnostics use bounded type chains, not raw exception/message text;
- query strings, credentials, secret-like fields, and unknown context keys are omitted.

### Metrics

Use `prometheus-client` for Prometheus-compatible metrics.

Do not require a Prometheus/Grafana deployment in the base Compose stack; expose metrics and provide optional examples/documentation.

### Tracing

OpenTelemetry may be added as an optional instrumentation layer if implemented without becoming a hard runtime dependency for ordinary self-hosting. It is not required for V1 completion unless the implementation adopts it consistently.

---

## 21. Python code-quality standards

### Ruff

Use Ruff for:

- linting;
- import sorting;
- formatting.

Do not run Black/isort as parallel formatters when Ruff owns these concerns.

### Type checking

Use Pyright in strict project configuration. Run backend/shared-contract and generic-runtime
checks package-scoped because both distributions intentionally expose a top-level `app` package;
do not combine those independent import roots into one synthetic analysis environment.

At minimum enforce:

- typed public functions/methods;
- no implicit optional;
- warnings for unnecessary ignores;
- disallow untyped defs in application code;
- explicit third-party exemptions only when stubs are unavailable.

`Any` is permitted only at raw untrusted JSON/SDK boundaries and should be validated/narrowed immediately.

### Design style

- async I/O for FastAPI and network/database clients;
- dependency injection through constructors/factories;
- protocols/ABCs for external semantic interfaces;
- dataclasses/Pydantic models rather than unstructured dicts across domain boundaries;
- enums/value objects for states;
- no global mutable clients initialized at import time;
- no broad `except Exception` without rethrow/normalization at process boundaries.

---

## 22. TypeScript/code-quality standards

Use:

- TypeScript strict mode;
- ESLint with React/TypeScript rules;
- Prettier only if formatting is not fully covered by the selected ESLint/toolchain;
- no `any` except generated/validated boundary code with justification;
- feature folders over giant generic component directories;
- server state in TanStack Query;
- form state in RHF;
- local UI state in React;
- no Redux unless a future state problem objectively requires it.

---

## 23. Testing stack

### Python

Use:

- `pytest`;
- `pytest-asyncio`;
- `pytest-cov`;
- `respx` for httpx mocking;
- factory/fixture helpers kept lightweight;
- Docker Compose/integration fixtures for real Postgres/Redis/Milvus/runtime tests.

### Frontend

Use:

- Vitest;
- React Testing Library;
- MSW if API mocking improves feature tests;
- Playwright for Chromium, Firefox, WebKit, and compact mobile E2E;
- strict TypeScript compilation of E2E fixtures/mocks against the same generated DTO contract as
  production frontend code.

### MCP

Use:

- official MCP client library;
- MCP Inspector for manual/debug compatibility;
- automated runtime protocol suite that starts the production runtime factory and requires a
  successful schema-valid call for every enabled tool; an MCP error result never counts as success.

### Test policy

Tests are layered:

1. pure unit/golden tests — fast, default PR gate;
2. backend DB/client integration — CI service profile;
3. Milvus/OpenRouter contract — Milvus real, OpenRouter fake by default/live optional;
4. Docker runtime/deployment integration;
5. Playwright E2E.

Live paid OpenRouter calls must not be required for every contributor PR.

---

## 24. Security/release tooling

Approved release/security tools:

- Gitleaks for secret scanning;
- Trivy for container/filesystem vulnerability scans;
- pip-audit (or an equivalent maintained Python advisory scanner compatible with uv lock/export);
- digest-pinned OSV-Scanner checks for the complete pnpm lockfile;
- Syft for SBOM generation;
- Cosign for image signing when release infrastructure is configured;
- GitHub Dependabot as the canonical automated dependency PR mechanism; do not configure Renovate in parallel.

GitHub code scanning may add CodeQL, but it should complement—not replace—tests and dependency scans.

---

## 25. Package management

### Python — uv

Use uv workspaces and a single authoritative lockfile where practical.

Rules:

- no ad hoc `pip install` instructions for development;
- Docker builds install from locked dependencies;
- dependency groups for dev/test;
- runtime package dependency set kept separate/minimal.

### JavaScript — pnpm

Use pnpm and commit `pnpm-lock.yaml`.

Node version pinned via `.nvmrc`/`.node-version`/Volta/Corepack policy as chosen; use Node 24 LTS.

Do not commit npm/yarn alternative lockfiles.

---

## 26. Configuration standards

Use environment variables for installation/runtime configuration, parsed by Pydantic Settings.

Ship `.env.example` with **names and safe examples only**, never real secrets.

Configuration groups:

- application/public URLs;
- PostgreSQL;
- Redis;
- Milvus;
- artifact paths;
- OpenRouter secret/model defaults;
- encryption master key reference;
- MCP base domain;
- Traefik/deployment network/image configuration;
- upload/fetch/build limits;
- logging/metrics;
- development flags.

Configuration must be validated at startup and fail with clear messages for missing required production settings.

---

## 27. Dependency boundary rules

The following imports are forbidden outside designated modules:

| Dependency/SDK                         | Allowed location                                  |
| -------------------------------------- | ------------------------------------------------- |
| SQLAlchemy engine/session creation     | `clients/database` and persistence bootstrap      |
| `redis` client                         | `clients/cache`                                   |
| `pymilvus`                             | `clients/vector`                                  |
| OpenRouter/raw provider HTTP specifics | `clients/ai` / `providers/ai`                     |
| Docker Python SDK                      | `clients/docker` only                             |
| MCP client                             | `clients/mcp` and tests                           |
| MCP server SDK                         | `mcp_runtime/server` (plus protocol test harness) |
| filesystem writes for artifacts        | storage client/provider                           |

CI should include import-boundary/grep tests where practical.

---

## 28. Explicitly rejected technology choices

Unless the authoritative docs are later changed, do not introduce:

- Django;
- Flask as a parallel backend;
- Next.js;
- pgvector;
- another vector database;
- LangChain/LangGraph;
- Celery/RabbitMQ;
- Kafka;
- Kubernetes requirement;
- Terraform requirement for basic install;
- GraphQL application API;
- microservices;
- multiple ORMs;
- Material UI/Ant Design parallel UI system;
- generated project-specific Python MCP codebases;
- proprietary billing/subscription SDKs.

---

## 29. Rationale summary

| Decision                              | Why                                                          |
| ------------------------------------- | ------------------------------------------------------------ |
| FastAPI/Pydantic                      | Typed Python API and shared schema-heavy design              |
| PostgreSQL                            | Durable relational authority and JSONB support               |
| Redis/RQ                              | Simple self-hosted job/cache infrastructure                  |
| Milvus                                | Explicit dedicated vector-store requirement                  |
| OpenRouter                            | One build-time gateway for structured AI + embeddings        |
| Official MCP Python SDK               | Protocol correctness and exact-schema runtime support        |
| Manifest-driven runtime               | Maintainability, reproducibility, shared security fixes      |
| React/Vite                            | Internal SPA without SSR complexity                          |
| Tailwind + shadcn/ui                  | Requested modern UI stack with repository-owned components   |
| Docker Compose                        | Appropriate self-hosted operational complexity               |
| Traefik                               | Dynamic Docker routing per project subdomain                 |
| uv/pnpm                               | Fast deterministic package management/lockfiles              |
| client/provider/repository boundaries | Replaceability, testability, consistent errors/observability |

---

## 30. External compatibility references

The implementation should validate upgrades against official upstream documentation. At the specification date:

- official MCP Python SDK documentation identifies v2 as stable and supports Streamable HTTP/exact-schema low-level usage;
- OpenRouter documents JSON-Schema structured output and embeddings endpoints;
- PostgreSQL 18 is the current stable major line and 18.6 is a current maintenance release;
- Milvus documents a standalone Docker Compose deployment in its current 3.x documentation;
- Traefik documents Docker label-driven routing and explicitly warns against storing secrets in labels;
- React documentation identifies 19.2 as the latest major/minor documentation line;
- Vite documentation lists 8.2 as the current regularly patched supported line;
- Tailwind documents the 4.3 release line;
- Node 24 is an LTS line in August 2026.

---

## 31. Technology-stack completion criteria

The stack is correctly implemented when:

1. all production dependency versions are locked;
2. the approved major technology families are used and rejected parallel stacks are absent;
3. PostgreSQL/Redis/Milvus roles match architecture;
4. no pgvector dependency/schema exists;
5. `mcp_runtime` dependency graph contains no OpenRouter/Milvus/PostgreSQL/Redis/Docker builder dependencies;
6. external SDK usage respects client/provider boundaries;
7. base Compose uses pinned supported service images;
8. Node/Python toolchains are pinned and reproducible;
9. lint/type/test/security tooling runs in CI;
10. SBOM/vulnerability scanning is included in release validation.
