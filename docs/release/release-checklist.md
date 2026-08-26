# Production release checklist

Every checked item needs a link or stored evidence record. Unchecked means not ready.

## Repository and governance

- [ ] `master` protection, required CI/security/CLA/CODEOWNERS review, and force-push/deletion controls are enabled.
- [ ] Founder-approved individual/entity CLA text and verification service are operational; no external PR bypassed it.
- [ ] Private vulnerability reporting and conduct-reporting channel work.
- [ ] License, trademarks, maintainers, governance, sponsorship, generated-output, contribution, and security documents are current.

## Product and contracts

- [ ] All authoritative acceptance scenarios map to live routes/UI behavior with no production mock/stub/TODO or parallel implementation.
- [ ] OpenAPI, typed clients, domain contracts, migrations, compiler/runtime schemas, and generated artifacts agree.
- [ ] Source provenance, explicit exclusions, deterministic executable mapping, 100% coverage, no blocking findings, and runtime compatibility are proven.
- [ ] Auth/CSRF/roles, one-time secret handling, SSRF/redirect/DNS policy, manifest digest, runtime isolation, and failed replacement/rollback behavior pass negative tests.

## Quality and supply chain

- [ ] Formatting, lint, type checks, backend/runtime/contracts tests, frontend unit/build, Chromium/Firefox/WebKit/mobile E2E, and Compose/image smoke tests pass from frozen locks.
- [ ] Secret, dependency, repository misconfiguration, and all three image scans have no unaccepted HIGH/CRITICAL blocker.
- [ ] SBOMs, release evidence, checksums, image digests, and Cosign signatures verify for the exact tagged SHA.

## Operations

- [ ] Production DNS/TLS, redirect, security headers, secure cookies, unknown-host denial, and authenticated `/mcp` pass live validation.
- [ ] Unique production secrets, key escrow/versioning, least-privilege database/storage, network exposure, Docker socket separation, and host permissions are reviewed.
- [ ] Monitoring/log redaction, incident contacts, capacity/timeouts, retention, upgrade, and project rollback are rehearsed.
- [ ] Encrypted backup and isolated restore drill recover database, artifacts, encrypted credentials, indexes, and an authenticated runtime within accepted RPO/RTO.

## Sign-off

- Release/tag:
- Commit SHA:
- Evidence bundle/checksum:
- Technical reviewer:
- Security/operations reviewer:
- Founder release approval:
- Known residual risks and expiry:
