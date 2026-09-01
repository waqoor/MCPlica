# Post-merge validation — 2026-09-01

## Baseline and scope

Baseline: `435447656ea0fe21e50c3ac43440bc33448b1570` on `master`, after PR #21.
The exact tracked snapshot was obtained from CI run `33523113658`, source artifact
`9806523726`, SHA-256
`305097958b6194e282e4c0d70811d4bfb0aa23357a3e1bbc435af881dbe27f81`.
Its extracted Git tree matched `e1139439a75244782aa900b21b9ba9bf7cd9ed98`.

The baseline inventory contained 681 tracked files and 123,569 text lines. All 357
tracked Python files were syntax-parsed. Inventory/syntax checks are not a claim
that every line was semantically audited. Detailed review in this round focused on
source/canonicalization/indexing boundaries, runtime response validation, fixture
lifecycle, Docker contexts/networking, and operational/test commands. The 55-item
older audit and 32-feature backlog are not declared completely resolved or delivered.

## Confirmed corrections

| Area | Correction | Regression coverage |
| --- | --- | --- |
| Vector isolation (`ISS-002-001`) | Project/generation/source-aware documentation and semantic chunk identities; content-cache keys preserved. | Identical content across projects/generations survives repeat upsert and targeted cleanup, including real Milvus. |
| Exclusion input (`ISS-002-019`) | Reject non-string raw JSON before text normalization. | Null, numbers, booleans, lists, and objects yield field validation errors instead of AttributeError. |
| Response dispatch (`ISS-002-028`) | Exact status, then class, then default precedence is resolved before media validation. | An incompatible specific response cannot be accepted through a default response. |
| Canonicalization memory (`ISS-002-013`, bounded correction) | Read executable inputs sequentially; never fetch documentation bodies in this phase. | Storage spy permits only executable reads; existing parser/provenance behavior retained. Aggregate parsed-spec memory remains bounded only by existing input limits. |
| Acceptance cancellation | Detect outstanding owner cancellation before polling and after transport completion. | Deterministic cancellation-consuming transport plus real socket lifecycle tests. |
| Docker build inputs | Exclude runtime state, nested private environments, and private keys/certificates. | Docker copies a synthetic context without private files but retains examples/source. |
| Edge networking | Network name and explicit API/UI routing labels follow the configured edge network. | Static and resolved production checks; full Compose workflow uses a non-default edge. |
| Developer environment | Install and run targets share absolute per-package Python environment paths and frozen resolution. | Make dry-run assertions plus component CI. |

No schema migration, alternate architecture, duplicate runtime, approval workflow,
canary/shadow deployment, or tests in normal deployment startup is introduced.

## Upgrade considerations

New vector generations use new identifiers. Rebuild affected projects from retained
source versions through the existing build service. Historical collision damage
cannot be repaired merely by upgrading the executable; retain immutable historical
artifacts, do not rewrite them, and never purge a shared collection to conceal loss.
Response validation is intentionally stricter for malformed upstream responses.
Keep runtime secret files outside the repository and retain the installation's
existing environment/encryption keys. Follow the backup and upgrade runbooks.

## Local results and execution boundary

Before correction, the new focused regression selection produced 16 failures and
six passes. After correction, the 22 chunk/input/fixture checks passed. The expanded
selection including Compose/Make checks passed 28 tests. The runtime
response-contract suite passed eight tests; an expanded response/request/network/auth
selection passed 18. These overlapping selections are not additive repository test
counts. The starter validation checked 32 required files successfully.

These local checks used available Python 3.13 dependencies, not the exact repository
lock. Frozen local installation could not complete because outbound dependency DNS
was unavailable; there is no local Docker daemon. Therefore actual Compose/image,
frozen component, and live browser results come from the GitHub Docker runner.
Local tests alone do not establish a passing frozen or full-stack execution.

## Fresh CI evidence

Verified code commit: `ea88b9cf5f8967475e6644f5b8e5ea2a58abd0e9`, PR #22.
Git tree: `a90f4295eb8c672c48e346044fa80085c96bedcb`.
The final documentation/evidence commit does not change that implementation or its
CI definitions. GitHub validated the PR merge candidate against the unchanged
baseline master; the source tree was also checked against the local corrected tree.

| Verification | Actual result |
| --- | --- |
| CI run `33528770202`: backend | Passed frozen installation, formatting/lint, type checks, PostgreSQL migrations, tests, critical-module coverage, and schema-drift detection. |
| Same run: runtime | Passed frozen installation, formatting/lint, type checks, and tests. |
| Same run: frontend | Passed frozen installation, formatting/lint, types, unit tests, API contract/assets checks, and production build. |
| Same run: cross-browser | Passed: 16 successful cases, zero failures/flaky cases, eight explicit skips. This suite uses controlled API fixtures. |
| Same run: Docker | All steps passed, including three application image builds and canonical/production configuration checks. |
| Docker build-context privacy | Passed using Docker's actual exclusion engine and synthetic private files. |
| Real Milvus | Passed cross-project/generation documentation and semantic upserts, repeated-upsert idempotency, and scoped cleanup. |
| Real isolated project runtime | Passed separate two-project isolation/replacement/rollback acceptance. |
| Live Compose browser | Chromium: one passed, zero failed/flaky/skipped. |
| Final service state | All 13 expected: 11 healthy running services; migration and runtime initializer exited 0. |
| Security run `33528770143` | Passed secret scanning, locked Python/pnpm dependency audits, repository scan, and SBOM step. |

The full-stack workflow passed source/document ingestion, credential configuration,
indexing/retrieval, enrichment/validation, immutable build/export, authenticated MCP
calls for four HTTP methods, service/provider outage survival and recovery, changed
source/rebuild/diff, redeployment, rollback, and active-state plus MCP-call persistence
after database/cache/control-plane container recreation. It used a non-default edge
network. The workflow took 83.438 seconds in this fixture run; this is not a load or
capacity benchmark. It advertised four tools initially, five after rebuilding, and
four after rollback. Both fixture builds had 100% generated-operation coverage,
not 100% repository line or behavior coverage.

The Compose artifact `9809201659` was downloaded and its SHA-256 verified:
`e7a4510917e93d5d1161dea27ab9cacdce2d58ebc49e7a10341fe8039fdd9d58`.
Its workflow/service JSON and embedded live browser report were independently read.
The cross-browser artifact `9808965375` was also checksum-verified:
`80276c54b4b71bbef4f06e99a0925cbe129c1cd56425e7e8c85d27bb27bac34b`.
Non-secret extracts are retained in `post-merge-2026-09-01/`; raw private environment
values and raw logs are not committed. CI removed its disposable resources after
collecting evidence. No production machine was deployed or left running.

### CI status qualification

CI `33528770202` is **overall failed**, solely due to the separate dependency-review
job (`99926257806`), whose log explicitly says this repository does not support
dependency review and requires the relevant dependency-graph/security feature.
The five application/acceptance jobs all passed. No failing application test was
skipped or check disabled to obtain that result. Do not portray separate successful
package audits as successful GitHub dependency review. Repository feature settings,
visibility, paid features, and protections were not changed. The existing CLA
integration remains outside this correction round.

### Precise design clarification

For the current implementation, the older source-only chunk-ID description in
`design_document.md` section 12.2 is superseded by the namespace-aware identity above.
Determinism holds within the same project/generation/source binding; only the text
content hash, not the stored row primary key, is shared for embedding-cache reuse.
Response status precedence is exact status, then status class, then default;
media validation occurs only within the first declared status definition.

## Remaining external and review boundaries

No live commercial model credentials, production DNS/ACME, production server,
release publication/signature evidence, or encrypted backup restoration was supplied.
HTTP provider/upstream fixtures are explicit test inputs; the application stack,
Docker runtimes, database, queues, and vector store are real in Compose acceptance.
GitHub PR dependency-review feature availability and the existing CLA integration
remain separate repository prerequisites; no protection or security check is removed.
