# MCPlica documentation

## Authoritative product documents

These six documents define scope and implementation authority. Later explicit decisions override earlier conflicts.

1. `architecture.md` — boundaries and system architecture.
2. `design_document.md` — technical design and contracts.
3. `product_requirements.md` — product and acceptance behavior.
4. `implementation_plan.md` — implementation phases and gates.
5. `tech_stack.md` — technology and engineering standards.
6. `open_source_and_sponsorship_model.md` — governance, CLA, ownership, and sustainability.

## User and API

- `user-guide.md` — roles, ten-step setup, workspaces, recovery, and accessibility.
- `api.md` — authentication, requests, responses, pagination, async work, and contract changes.
- `api-inventory-v1.md` — registered control-plane route/security inventory.
- `mcp-client-connection.md` — static bearer/OIDC client connection and diagnosis.
- `compatibility.md` — supported platforms, dependency baseline, client matrix, and limitations.

## Operations and security

- `operations/installation.md`
- `operations/configuration.md`
- `operations/docker-compose.md`
- `operations/domain-tls.md`
- `operations/backup-restore.md`
- `operations/upgrade.md`
- `operations/troubleshooting.md`
- `operations/runbook.md`
- `security/threat-model.md`
- `security/hardening.md`

## Release evidence

- `../VERSION` — authoritative release version; generated copies are checked in CI.
- `../CHANGELOG.md` — user/operator-visible history and changelog policy.
- `releases/v1.0.0.md` — v1.0.0 release notes, migration guidance, limitations, and final commands.
- `release/release-process.md`
- `release/release-checklist.md`
- `evidence/v1.0.0-release-candidate.md` — current release-preparation results and external gates.
- `evidence/post-merge-validation-2026-09-01.md` — historical post-merge regression snapshot.
- `evidence/compose-validation-2026-09-01.md` — historical Compose corrections, commit-bound CI results, and verification boundaries for its stated snapshot.
- `evidence/final-integrated-validation.md` — historical traceability and local execution proof for its stated snapshots.
- `evidence/issues-001-closure.md` — historical second-round status for 48 findings; the source register is not shipped, so this ledger is not current-release proof by itself.
- `evidence/issues-002-closure.md` — verified disposition and implementation/runtime evidence for all 55 `issues_002.md` findings, including migrations `0021`–`0025`, PostgreSQL concurrency, Docker/Compose, contracts, frontend, and security boundaries.
- `evidence/issues-002-foundation-closure.md` — focused reproduction, implementation, migration,
  concurrency, runtime, and operational proof for `ISS-002-002` through `ISS-002-009`.

Root-level legal/community policy remains authoritative for contributors: `LICENSE`, `CLA.md`,
`CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `GOVERNANCE.md`, `MAINTAINERS.md`, `SECURITY.md`,
`SUPPORT.md`, `SPONSORSHIP.md`, `TRADEMARKS.md`, and `GENERATED_OUTPUTS.md`.
