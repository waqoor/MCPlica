# Technical overview

> A condensed, narrative explanation of the system for readers who want the shape of it without
> reading the full specification set. [`architecture.md`](architecture.md) and
> [`tech_stack.md`](tech_stack.md) remain authoritative for implementation detail; this document
> summarizes them.

MCPlica is a self-hosted, open-source platform that turns an OpenAPI or API Inventory description
of an existing API into a deployed **MCP server** — a standards-based endpoint that AI agents/hosts
can call as tools, without anyone hand-writing an MCP integration. It is not a chat product and
does not run agents itself; it terminates at the MCP endpoint and hands off to whatever
MCP-compatible client the company connects.

**Non-negotiable constraints that shape every design decision:**

- No multi-tenancy, billing, or subscription model — one installation, many independent projects.
- One isolated MCP runtime and subdomain per project.
- OpenRouter (AI) is build-time only; a deployed runtime never depends on it.
- Milvus (vectors) is builder-side only; a deployed runtime never depends on it.
- One reusable generic runtime image, not one generated codebase per project — projects are
  compiled *manifests*, not separate applications.
- Deterministic structure, AI-assisted semantics: HTTP methods, paths, schemas, and security
  schemes come from parsing the source, never from AI guessing; AI may only enrich descriptions.
- Fail-closed: missing credentials, invalid mappings, or unsupported schemas fail the build or
  disable the operation — never silently guessed.

## System architecture

```text
        Web UI (React)  ──▶  FastAPI
                                 │
        ┌──────────┬────────────┼────────────┬──────────────┐
        ▼          ▼            ▼            ▼              ▼
   PostgreSQL    Redis        Milvus     OpenRouter     Runtime Manager
                                                              │
                                                    create / deploy
                                                              ▼
                                                          Traefik
                                                              │
                                    ┌─────────────────────────┼─────────────────────────┐
                                    ▼                         ▼                         ▼
                            Project Runtime            Project Runtime            Project Runtime
                                    │                         │                         │
                                    ▼                         ▼                         ▼
                             Company API                Company API                Company API
```

The Builder/Control Plane (top) compiles projects into manifests; the MCP Serving Plane (bottom)
only executes them. No arrow points from the Serving Plane back to OpenRouter or Milvus — a
deployed runtime has no dependency on either, so it keeps working even if build-time AI or the
vector index is down.

## Core components

- **Web UI** — React/TypeScript admin interface; talks only to the FastAPI application API.
- **FastAPI** — the application boundary. Routers stay thin and delegate to application services;
  they never touch the database, Docker, or external APIs directly.
- **PostgreSQL** — authoritative state: users, projects, sources, builds, deployments, encrypted
  credentials, audit history.
- **Redis** — non-authoritative, rebuildable: RQ job queues, progress events, short-lived locks,
  caches. Losing it can interrupt an active job but never loses authoritative state.
- **Milvus** — semantic vector index over project documentation and source descriptions,
  rebuildable from source versions plus embedding configuration.
- **OpenRouter** — build-time AI: semantic classification, description enrichment,
  documentation-to-operation correlation, and embeddings. Every AI response used by the pipeline is
  parsed into a typed, structured schema — it never directly edits executable behavior.
- **Runtime Manager** — the only component with Docker access; the FastAPI web process itself
  never touches the Docker socket. It creates, health-checks, and replaces per-project runtime
  containers.
- **Traefik** — edge reverse proxy; only explicitly labeled MCP containers are routed, each at its
  own subdomain.

## Build-time data flow

One build is one immutable attempt to compile a project's current source versions into a
deployable artifact:

1. **Source ingestion** — sources are content-hashed and versioned; every version is immutable
   once created.
2. **Deterministic parse/normalize** — OpenAPI/API Inventory syntax and version are validated,
   references resolved, and servers/security schemes/operations extracted into a **canonical API
   model**. This model, not the raw source, is the only executable input downstream.
3. **Documentation branch (parallel)** — documentation is chunked, embedded via the configured
   OpenRouter model, and indexed in Milvus alongside deterministic chunks from the canonical model
   itself.
4. **AI analysis** — OpenRouter uses retrieval from that index to enrich descriptions and
   terminology through a declared structured-output schema, parsed into typed models. No AI output
   can overwrite source-derived executable structure.
5. **Deterministic compilation** — the enriched canonical view compiles into a versioned MCP
   manifest: tool names, input schemas, HTTP request mappings, auth mapping references.
6. **Validation** — source, canonical, coverage (100% of operations after explicit exclusions),
   schema, security-mapping, semantic, MCP-protocol (an actual isolated runtime lists tools and
   executes a real schema-valid call per tool), and artifact checks all run; a build cannot reach
   `READY` unless every blocking check passes.
7. **Immutable build** — the result, with full provenance (exact source versions, compiler
   version, AI model IDs, manifest hash), is recorded and never mutated afterward. An explicit
   rebuild creates a new build.

## Deployment and runtime isolation

Every project gets its own container, its own immutable manifest mount, its own secret mount, its
own resource limits, its own subdomain (`<slug>.mcp.<domain>`), and its own Docker network
containing only that runtime and its Traefik attachment — no connection to PostgreSQL, Redis,
Milvus, or the Docker socket. Hardening baseline: non-root user, read-only root filesystem, no new
privileges, dropped Linux capabilities, no host network, no privileged mode.

**Deploying is health-before-switch**, never in-place: a new runtime is created, its exact
container and Traefik-edge identity are re-verified, and only after it reports healthy does it
become the active one. A failed replacement never touches the previously healthy runtime — the old
one keeps serving traffic. Rollback works the same way: it redeploys a previously-validated build
as a *new* deployment record rather than mutating history, and only from a deployment with proven
successful activation evidence.

## Authentication boundaries

Two independent authentication directions exist and are never conflated:

- **MCP client → runtime (inbound).** Protects the published MCP endpoint itself. Static
  high-entropy bearer tokens are the interoperable baseline — shown once at creation, stored only
  as hashes. External OAuth/OIDC is also supported. Disabling auth entirely exists only as an
  explicit development-mode setting, never a production default.
- **Runtime → company API (outbound/upstream).** The credential the deployed runtime uses to call
  *your* API, mapped from the source's declared security schemes (bearer, API key header/query,
  HTTP Basic, OAuth2 client credentials, static headers). These secrets never become MCP tool
  arguments and are never written to manifests, logs, or export bundles.

An allowlisted-host SSRF policy bounds both outbound upstream calls and any builder-side remote
source fetch: no arbitrary scheme/host/port from tool arguments, redirects revalidated against the
allowlist, link-local/loopback/metadata destinations blocked by default.

## Data ownership

- **PostgreSQL — authoritative.** Every durable domain fact: users, projects, source metadata and
  immutable versions, canonical snapshots, builds, validation reports, deployments, encrypted
  credentials, audit/activity events.
- **Redis — transient/rebuildable.** Job queues, progress fan-out, short-lived locks, caches. Loss
  can interrupt an in-flight job but never loses authoritative state.
- **Milvus — rebuildable semantic index.** Vectors and searchable metadata derived from
  documentation and source descriptions. PostgreSQL records the index generation and the embedding
  model/dimensions needed to interpret it, so the index can always be regenerated from source
  truth.
- **Artifact storage (local filesystem in v1).** Immutable source blobs and generated/export
  artifacts, referenced by content hash. Designed to move to object storage later without changing
  domain behavior.

## Technology stack

All production dependencies are pinned through lockfiles or image digests — no floating `latest`
tags.

| Area | Baseline |
| --- | --- |
| Python | 3.13.x |
| Node.js | 24 LTS |
| React | 19.2.x |
| Vite | 8.2.x |
| Tailwind CSS | 4.3.x |
| PostgreSQL | 18.x (18.6 at spec date) |
| Redis | 8.x |
| Milvus | 3.x standalone |
| MCP Python SDK | 2.x, pinned 2.1.1, protocol `2026-07-28` |
| Traefik | v3 |

Deployment is Docker Compose on a single host by default: `traefik`, `frontend`, `api`, `worker`,
`postgres`, `redis`, `milvus` (plus its supporting services), with dynamically created per-project
runtime containers managed by the Runtime Manager — those are not statically enumerated in the base
Compose file.
