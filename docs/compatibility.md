# v1 compatibility and support matrix

This document defines the tested and supported `1.0.x` release boundaries. A dependency appearing
in a lockfile does not by itself prove every host/client/provider combination.

## Product and contract versions

| Surface                     | v1.0.0 contract                                             | Compatibility rule                                                                                                               |
| --------------------------- | ----------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Product/packages/API/images | `1.0.0` from root `VERSION`                                 | Release tag must be exactly `v1.0.0`; all copies are CI-checked                                                                  |
| Control-plane REST API      | `/api/v1`                                                   | Additive compatible changes stay in v1; breaking changes require a new major release                                             |
| MCP manifest                | `mcp-manifest/v1`                                           | Schema identifier is independent of the product patch version                                                                    |
| Generic runtime             | `1.0.0`                                                     | A build declares a PEP 440-compatible runtime range and deployment checks it before activation                                   |
| MCP transport/protocol      | Streamable HTTP at `/mcp`; validation revision `2026-07-28` | Client must negotiate a revision supported by the official SDK, the deployed JSON Schemas, and the configured bearer/OIDC header |
| Database                    | Alembic `0025`                                              | One linear migration head; follow release-specific upgrade and downgrade constraints                                             |

## Supported deployment and development platforms

| Environment                                        | Support status                   | Requirements and boundary                                                                                                                                                       |
| -------------------------------------------------- | -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Linux x86-64 production host                       | Supported topology               | Docker Engine, Docker Compose 2.24.4+, systemd/host operations, ports 80/443, writable Docker socket for deployment worker, and at least the configured Milvus/runtime capacity |
| Linux x86-64 GitHub runner                         | CI target                        | Component, migration, browser, security, image, and disposable Compose gates run here after push/PR                                                                             |
| Windows 10/11 with Docker Desktop Linux containers | Development and local acceptance | Use PowerShell-safe commands where documented; production promotion still requires a hardened Linux host                                                                        |
| macOS with Docker Desktop                          | Not certified for v1.0.0         | Expected development path only; no release evidence currently proves the full dynamic-runtime workflow                                                                          |
| Linux arm64                                        | Not certified for v1.0.0         | Upstream images may be multi-architecture, but the complete release candidate has no arm64 acceptance evidence                                                                  |
| Kubernetes, Swarm, Podman, rootless Docker         | Not supported by v1.0.0          | No alternate deployment architecture or compatibility layer is shipped                                                                                                          |

The default Milvus limit is 8 GiB. Size the host for PostgreSQL, Redis, etcd, MinIO, the control
plane, build workers, and every concurrently active 512 MiB project runtime in addition to it.

## Toolchain and service baseline

| Dependency         | Required/locked line                                                                |
| ------------------ | ----------------------------------------------------------------------------------- |
| Python             | `>=3.13,<3.14`; container baseline 3.13.15                                          |
| uv                 | Container/release baseline 0.12.9; use a compatible current uv for host development |
| Node.js            | `>=24,<25`; `.node-version` pins 24.16.0                                            |
| pnpm               | 11.25.0 through Corepack                                                            |
| PostgreSQL         | Compose image 18.6 by immutable digest                                              |
| Redis              | Compose image 8.2 Alpine by immutable digest                                        |
| Milvus             | Compose image 3.0.1 by immutable digest                                             |
| Traefik            | Compose image 3.7.12 by immutable digest                                            |
| NGINX unprivileged | Frontend runtime image 1.31.4 Alpine slim by immutable digest                       |
| MCP Python SDK     | Locked 2.1.1 in backend/runtime; candidate validation pins protocol `2026-07-28`    |

Use the committed `uv.lock`, `frontend/pnpm-lock.yaml`, and digest-pinned Compose/base images.
Dependencies are updated only through reviewed lock/digest changes with CI and security evidence.

## MCP clients and identity providers

MCPlica is client-neutral. A compatible client must support MCP Streamable HTTP, the runtime's
advertised tool/resource schemas, HTTPS in production, and an `Authorization: Bearer` header for
static or external OIDC access. Every candidate runtime is validated with the official SDK using
the latest supported revision, `2026-07-28`; the same canonical runtime also retains tested
`2025-11-25` negotiation compatibility for existing clients. No named desktop/editor client is
certified solely because it can store an HTTP MCP URL; verify initialize, list, schema-valid call,
error, and token rotation against the target release.

External OIDC requires an HTTPS issuer, exact audience, configured algorithms/JWKS, required
scopes, and normal clock/expiry handling. Provider-specific discovery, login UX, and availability
remain external prerequisites.

## Known limitations

- Local filesystem artifacts and a Docker-host runtime root are authoritative alongside
  PostgreSQL; backup consistency is an operator responsibility.
- Redis is transient queue/cache state. Milvus indexes are rebuildable, but rebuilding can require
  the configured embedding provider and retained source artifacts.
- There is no in-product backup scheduler, multi-host failover, hosted monitoring service, or
  automatic disaster-recovery promotion.
- The build plane requires configured OpenRouter models for real AI-assisted builds. Test fixtures
  prove protocol behavior, not live model availability, quality, quota, or cost.
- The product intentionally excludes chat, autonomous agents, HITL approval gates, SaaS tenancy,
  billing, and entitlement systems.
- Public DNS, certificates, email/incident channels, organization rulesets, registry/OIDC
  permissions, and external CLA status are not created or certified by local tests.
