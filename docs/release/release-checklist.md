# Production release checklist

Every checked item needs an exact URL, workflow run, command output, or stored evidence record for
the release commit. “Not applicable” needs a written reason. An unchecked/unknown item means the
release is not ready; local evidence cannot satisfy a hosted or production-host gate.

## Current v1.0.0 disposition (2026-09-03)

The exact branch, pull-request, dependency, hosted-log, repository-control, and external-gate
inventory is in the [current branch and release-gate
audit](../evidence/v1.0.0-branch-and-gate-audit.md). The previously integrated `master` head
`b22ff7e` is superseded as release evidence because its nominally successful E2E job contained a
WebKit failure that passed on retry. `fix/final-release-closure-20260903` contains the canonical
navigation correction, request-level regression, and fail-closed flaky-test policy. Its hosted
repository-control and documentation heads passed all ten hosted checks under the final
selected-action policy. Their replacement Docker artifacts independently matched GitHub's digest
and recorded all 13 required service states plus the complete workflow. Immutable results and the
exact 20-reference execution closure are in [PR #44](https://github.com/yazeedhasan97/MCPlica/pull/44).
Its dependency-remediation head `6d5abba` also passed all ten checks: CI
[33705386979](https://github.com/yazeedhasan97/MCPlica/actions/runs/33705386979), Security
[33705386981](https://github.com/yazeedhasan97/MCPlica/actions/runs/33705386981), and CLA
[33705384466](https://github.com/yazeedhasan97/MCPlica/actions/runs/33705384466). Artifact
`9875280973` independently matched GitHub's SHA-256 and recorded the same complete acceptance
surface. Embedding the current candidate hash here would change that hash; the exact final PR head
and its checks must therefore be retained in PR evidence after this refresh.

No independent review is currently requested: the only listed maintainer and CODEOWNER is the PR
author, and another account's repository write access is not an explicit governance appointment.
The founder must record an independent reviewer/maintainer appointment or scoped delegation before
requesting approval, so the PR remains deliberately unmerged.

Repository Actions now permits only the recursively audited 20-reference full-SHA closure; broad
GitHub-owned and verified-creator allowances are disabled. Workflow tokens default to read-only and
cannot approve reviews. Dependabot vulnerability alerts and automated security fixes are enabled.
Their asynchronous first response of zero alerts was provisional: the completed scan then opened
alert #1 for pytest GHSA-6w46-j5rx-g56g/CVE-2025-71176. The corrective branch now constrains both
Python projects to the patched pytest line, locks 9.1.1, and makes both frozen advisory audits cover
all optional development dependencies. Local Python 3.13 audit and compatibility evidence is clean;
the exact final hosted head must repeat the audits. Because Dependabot evaluates the default branch,
alert #1 must remain open until the independently approved correction is merged; GitHub must then
close it from the updated `master` graph before tagging. The CLA workflow remains fail-closed for
untrusted contributors. Branch
protection/rulesets, independent review, founder-approved external CLA service, GitHub private
vulnerability reporting/code scanning/secret scanning, target-host acceptance, backup/restore, and
publication evidence remain unchecked operator gates. No tag or Release exists.
The owner-assigned external-action ledger is [issue
#45](https://github.com/yazeedhasan97/MCPlica/issues/45).

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

- [x] Repository Actions permits only the recursively audited 20-reference full-SHA execution
      closure; broad GitHub-owned/verified-creator allowances are disabled, workflow tokens default
      to read-only, and workflows cannot approve reviews. The exact-policy CI/Security/CLA reruns
      are recorded in [PR #44](https://github.com/yazeedhasan97/MCPlica/pull/44#issuecomment-5518862289).
- [x] Dependabot vulnerability alerts and automated security fixes are enabled. The completed scan
      found alert #1 for pytest GHSA-6w46-j5rx-g56g/CVE-2025-71176; the corrective branch uses the
      patched 9.1.1 lock and audits all optional development dependencies.
- [x] Both hosted all-extras Python audits passed on dependency-remediation head `6d5abba`, each
      showing pytest 9.1.1 in the export and no known vulnerabilities. The documentation-only final
      head must repeat the same checks.
- [ ] After an authorized merge, GitHub has re-indexed the reviewed default-branch lock,
      automatically closed alert #1 as fixed, and reports zero open Dependabot alerts. Recheck
      again immediately before tagging.
- [ ] `master` protection/rulesets require pull requests, sensitive CODEOWNERS review,
      conversation resolution, current CI/Security/CLA checks, and block force pushes/deletion with
      administrator enforcement.
- [ ] Trusted repository actors are recognized from GitHub pull-request metadata, and the
      founder-approved CLA service plus `CLA_STATUS_CONTEXT` work for the exact head of every
      external contribution; no external contribution bypassed verification.
- [ ] GitHub private vulnerability reporting, code scanning, secret scanning, and the
      conduct-reporting channel work; maintainer access and release/OIDC/GHCR permissions were
      reviewed.
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
- [ ] Gitleaks, GitHub introduced-dependency review where the repository supports it, private-repo
      locked-graph `pip-audit`/`pnpm audit`, Trivy source/misconfiguration/secret scans, and all
      three pre-publication image scans have no unaccepted HIGH/CRITICAL blocker.
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
