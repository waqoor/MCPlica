# Production release checklist

Every checked item needs an exact URL, workflow run, command output, or stored evidence record for
the release commit. “Not applicable” needs a written reason. An unchecked/unknown item means the
release is not ready; local evidence cannot satisfy a hosted or production-host gate.

## Release identity and repository state

- [ ] `VERSION`, all package/lock/runtime/frontend/API/image consumers, `CHANGELOG.md`, and
      `docs/releases/vX.Y.Z.md` agree; `python scripts/release_version.py --check` passes.
- [ ] The release-preparation branch contains only intended reviewed changes; generated artifacts,
      documentation links, examples, and `MANIFEST.sha256` are current. The checksum manifest was
      regenerated from the fully staged Git index and then verified on a clean checkout.
- [ ] No tracked `.env`, secret, private source specification, runtime secret bundle, disposable
      output, review scratch, merge marker, placeholder release value, or ignored build product is
      present.
- [ ] The release-readiness pull request records exact local/hosted results, known limitations,
      external prerequisites, rollback/migration impact, and final publication commands.

## GitHub controls and governance

- [ ] `master` protection/rulesets require pull requests, sensitive CODEOWNERS review,
      conversation resolution, current CI/Security/CLA checks, and block force pushes/deletion with
      administrator enforcement.
- [ ] The founder-approved CLA service and `CLA_STATUS_CONTEXT` work for the exact pull-request
      head; no external contribution bypassed it.
- [ ] Private vulnerability reporting and the conduct-reporting channel work; maintainer access and
      release/OIDC/GHCR permissions were reviewed.
- [ ] License, trademarks, maintainers, governance, support, sponsorship, generated-output,
      contribution, security, release, label, issue, and pull-request policies are current.

## Product, contracts, and migrations

- [ ] Authoritative acceptance behavior maps to the canonical routes/UI/runtime with no production
      mock/stub/TODO, duplicate implementation, alternate persistence, or parallel deployment path.
- [ ] FastAPI OpenAPI, generated TypeScript/Zod clients, shared contracts/JSON Schemas, fixtures,
      compiler/runtime compatibility, migrations, and documentation agree.
- [ ] Blank database upgrade reaches the single `0025` head; `alembic check`, the safe
      `0025 -> 0020 -> 0025` rehearsal, legacy-constraint upgrade, and intentional `0021`
      downgrade-refusal scenario pass on PostgreSQL.
- [ ] Source/build identity, execution fencing, bounded I/O/lifecycle, pagination, key rotation,
      safe logging, structured-AI accounting, deterministic mapping, and exact 100% validation
      retain their PostgreSQL/component regression coverage.
- [ ] Authentication/CSRF/roles, write-only secrets, SSRF/redirect/DNS policy, artifact/manifest
      digests, runtime isolation, and failed replacement/rollback paths pass positive and negative
      tests.

## Quality and supply chain

- [ ] Frozen install, format, Ruff/ESLint, strict Python/TypeScript checks, backend/runtime/contracts
      tests, critical coverage floors, frontend unit/build, and Chromium/Firefox/WebKit/mobile E2E
      pass for the exact commit.
- [ ] Canonical Compose render/build/start, image metadata, Docker context, dynamic runtime,
      real-Milvus isolation, live browser, authenticated MCP calls, rebuild/redeploy, rollback,
      outage recovery, and persistence-after-recreation checks pass on a disposable Linux runner.
- [ ] Gitleaks, dependency review, `pip-audit`, `pnpm audit`, Trivy source/misconfiguration/secret
      scan, and all three pre-publication image scans have no unaccepted HIGH/CRITICAL blocker.
- [ ] `python scripts/checksum_manifest.py --check` passes and CI preserves the exact tracked source
      plus bounded/redacted diagnostics for the release commit.

## Publication artifacts

- [ ] The tag is annotated, exactly `v<VERSION>`, points to reviewed `master`, and neither its
      GitHub Release nor any matching GHCR image tag already exists.
- [ ] Backend/frontend/runtime image tags resolve to recorded immutable digests with correct
      version/source/revision/license labels and expected non-root users.
- [ ] Source and image SPDX JSON SBOMs, per-image release evidence/checksums, source archive,
      `SHA256SUMS`, Cosign bundle, image signatures, and registry provenance/SBOM attestations exist
      for the exact tagged SHA.
- [ ] Checksums, blob signature, every image signature, and provenance attestation verify using the
      tag-specific release workflow identity before any digest enters production configuration.

## Target production environment

- [ ] Supported hardened Linux x86-64 host has reviewed Docker/Compose versions, clock, capacity,
      disk/inodes, encryption, firewall, SSH/access, Docker socket controls, and runtime-root modes.
- [ ] Unique production secrets, encryption-key escrow/versioning, refresh/signing keys, database/
      storage least privilege, external provider credentials, and bootstrap-secret removal are
      verified without exposing values.
- [ ] UI/API/wildcard MCP DNS, TLS chain/hostname, redirect, security headers, secure cookies,
      unknown-host denial, and authenticated `/mcp` initialize/list/schema-valid call pass live.
- [ ] Real OpenRouter models/capabilities/quota, external OIDC where used, runtime upstream DNS/TLS,
      log redaction/monitoring/alerts, incident contacts, timeouts/capacity, and retention are tested.
- [ ] Encrypted backup and isolated restore recover PostgreSQL, artifacts, runtime root, keys,
      credential decryptability, indexes/rebuild path, active deployment evidence, and an
      authenticated runtime within accepted RPO/RTO.
- [ ] Upgrade and application rollback are rehearsed on a restored copy; project deployment
      rollback uses the canonical immutable-Build lifecycle.

## Sign-off

- Release/tag:
- Commit SHA:
- Pull request and required-check URLs:
- Evidence bundle/checksum:
- Technical reviewer:
- Security/operations reviewer:
- Release maintainer:
- Target-host evidence location:
- Known residual risks, owner, and expiry:
