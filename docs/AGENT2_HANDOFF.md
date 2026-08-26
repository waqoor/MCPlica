# Agent 2 handoff

**Status:** repository implementation for generic MCP runtime, runtime security, MCP access,
and dynamic deployment is complete in the shared checkout as of 2026-08-26. Target-host
promotion gates remain intentionally external.

## Delivered

- Exact-schema MCP Streamable HTTP runtime with tools/resources, deterministic HTTP mapping,
  all documented upstream auth modes, static/OIDC inbound auth, bounded/redacted errors, and no
  builder infrastructure dependency.
- Fail-closed manifest/secret/config loading, socket-bound DNS/SSRF enforcement, remote-schema
  reference rejection, bounded pooled clients, and hardened non-root runtime image.
- Canonical deployment/access models, repositories, services, jobs, APIs, and migration `0007`,
  integrated linearly beneath the shared `0008` head.
- Deployment-worker-only Docker authority; per-project networks; exact managed-resource
  identity; read-only/resource-limited containers; Traefik routing; health-before-switch;
  stop/restart/redeploy/rollback; retry/race/cleanup handling.
- One-time hashed MCP tokens and production-safe auth-mode/revocation coupling to live runtimes.
- Windows-compatible async migration runner without changing Linux behavior.

Full traceability and commands/results are in
`docs/evidence/agent2-runtime-deployment.md`.

## Final proof

- Runtime: Ruff/format clean, strict Pyright clean, **36 passed**.
- Backend: full Ruff and strict Pyright clean, **72 passed, 1 skipped**; all Agent 2 files
  format-clean. The opt-in Docker test passed separately.
- Real Docker with the final runtime image: **1 passed in 34.15s** for two-project isolation,
  replacement, rollback, peer survival, and cleanup.
- Contracts: quality/type gates clean, **2 passed**, generated schemas unchanged.
- Migration: offline render and fresh PostgreSQL `0001 -> 0008 (head)` passed; single head.
- Dev/production Compose, CI YAML, frozen runtime/backend image builds, and whitespace checks
  passed. No Agent 2/managed Docker resources remain.

## Shared/cross-agent changes

Canonical manifest/secret contracts, project active references, dependency/router/project hooks,
the `0007 -> 0008` migration edge, root lock/CI, Dockerfiles/Compose, and operator/security docs
were necessarily shared. Agent 2 introduced no alternate contract, model, runtime, deployment,
or persistence path.

At validation time, only seven Agent 1 files remained repository-format findings; they are listed
in the evidence file and were deliberately left to their owner.

## Production promotion gates

Supply immutable image digests, real DNS/ACME/TLS, unique credentials/OIDC metadata, constrained
Docker socket access where available, hosted CI/security evidence, monitoring, and recovery/
rollback drill evidence. Do not treat local images or placeholder domains as production proof.
