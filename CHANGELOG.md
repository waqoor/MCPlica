# Changelog

All notable MCPlica changes are recorded here. The format follows Keep a Changelog, and release
identities follow Semantic Versioning. Unreleased entries describe repository changes only; a
version is not published until its immutable tag and release workflow complete.

## [Unreleased]

### Changed

- Added an admin-only, route-backed **Settings > Providers** workspace for write-only encrypted
  OpenRouter key rotation, live connection testing, and distinct credential/reachability/build
  readiness states.
- Corrected the public OpenRouter API default and decoded-response header handling so compressed
  model-catalog responses cannot be decompressed twice and falsely degrade the control plane.
- Updated the official MCP Python SDK to 2.1.1, made `2026-07-28` the candidate-validation
  protocol revision, and retained explicit legacy negotiation coverage on the same runtime.
- Refreshed compatible container, frontend, Python, and GitHub Actions dependencies while
  preserving the Node 24, Python 3.13, and single-host service compatibility boundaries.
- Made each cleanup dispatch use one eligibility snapshot, preventing a failed target from
  consuming multiple retry attempts in the same worker cycle when its backoff is short or the
  database is under load.
- Bound the post-build wizard transition directly to the created build so an obsolete unbound
  journey refetch cannot race the URL back to the start-build step.
- Made hosted Playwright retries diagnostic only: any flaky retry now fails CI, with regression
  coverage that rejects post-build journey requests lacking the created build identity.
- Restricted repository Actions to the recursively audited full-SHA direct/transitive action
  closure, enabled Dependabot vulnerability alerts and automated fixes, and documented the exact
  unavailable private-platform security gates without treating local scans as substitutes.
- Updated the backend and runtime development constraint to pytest 9.1.1 for
  GHSA-6w46-j5rx-g56g/CVE-2025-71176, and expanded both frozen Python advisory audits to include
  every optional development dependency rather than auditing only the production graph.

## [1.0.0] - 2026-09-02

### Added

- Self-hosted FastAPI control plane, React administration UI, PostgreSQL persistence, Redis/RQ
  workers, Milvus document retrieval, and OpenRouter-backed build-time analysis.
- Deterministic OpenAPI 3.0/3.1 and API Inventory compilation into the shared
  `mcp-manifest/v1` contract, with source provenance, exact validation, immutable build evidence,
  export, diff, rebuild, and operation exclusion workflows.
- Reusable isolated MCP Streamable HTTP runtimes with static bearer or external OIDC inbound
  authentication, project-scoped upstream credentials, bounded HTTP execution, and dynamic
  Traefik routing.
- Health-before-switch deployment, stop/restart/redeploy, immutable-build rollback, durable
  command execution, fenced workers, retention cleanup, and recovery-safe lifecycle handling.
- Canonical Docker Compose development and production configurations, migration/init jobs,
  operator documentation, CI, security scanning, SBOM creation, checksums, digest signing, and
  provenance-aware release automation.

### Security

- Enforced cookie/CSRF/role authorization, encrypted write-only credentials, bounded uploads and
  external responses, SSRF/DNS/redirect controls, safe logging, non-root/read-only containers,
  resource limits, exact manifest/secret digests, and isolated runtime networks.
- Added frozen dependency locks, dependency and secret scans, pre-publication image scans,
  source/image SBOMs, Cosign verification, and immutable tag/digest refusal checks.

### Changed

- Established root `VERSION` as the `1.0.0` authority and synchronized package, API, frontend,
  runtime, Compose, image-label, generated-contract, fixture, lockfile, and release metadata.
- Advanced the single Alembic migration line through `0025`, including legacy constraint
  normalization, current-source/build identity, runtime/cleanup execution fencing, deployment
  intent, and index-generation ownership.

### Known limitations

- The supported production topology is a single Docker Compose host; high availability,
  orchestrator-specific deployment, managed backup automation, and multi-host runtime scheduling
  are not included.
- OpenRouter availability/model access, public DNS/TLS, host hardening, external OIDC providers,
  registry permissions, and backup/restore RPO/RTO remain operator-owned production checks.
- See [the v1.0.0 release notes](docs/releases/v1.0.0.md) for the complete compatibility,
  migration, and evidence boundary.

[Unreleased]: https://github.com/yazeedhasan97/MCPlica/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/yazeedhasan97/MCPlica/releases/tag/v1.0.0
