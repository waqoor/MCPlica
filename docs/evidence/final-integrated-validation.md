# Final integrated implementation and validation evidence

## 2026-08-27 second-round addendum

The `issues_001.md` second implementation round supersedes the historical repository counts
below for the current working tree. The exact 48-row disposition is in
`docs/evidence/issues-001-closure.md`: 22 findings are **VERIFIED COMPLETE**, 26 are
**FIXED IN SECOND ROUND**, none is **BLOCKED**, and no internally resolvable gap remains.

Current proof includes 240 backend/shared-contract passes with one skip and 72.203% aggregate
line coverage plus all critical-module floors; 54 runtime passes; 152 frontend unit passes; 16
isolated browser passes with 8 intentional project/viewport/live guards and retries disabled; and
one separately opted-in real-Compose Chromium pass. PostgreSQL reached `0020 (head)` from an empty
database, completed the `head -> base -> head` migration cycle, passed autogenerate/schema-drift
checks, and the current generic-runtime Docker/Traefik replacement, rollback, and two-project
isolation acceptance passed from the production-equivalent Linux worker boundary.
Ruff, Ruff format, package-scoped Pyright, TypeScript including E2E, ESLint, Prettier, generated
API drift, fixture drift, asset budgets, production builds, Compose validation, and locked runtime
image construction also passed. The dated 2026-08-26 record remains below as historical
first-round evidence rather than current counts.

**Validated:** 2026-08-26  
**Scope:** exact merged working tree on `master` at base commit `ac8cd85`  
**Environment:** Windows 10 / Docker Engine 29.2.0 / Compose 5.0.2 / Python
3.13.9 / Node 24.16.0 / pnpm 10.24.0 / uv 0.12.6

This document supersedes workstream-local verification counts and records the final
repository-wide state. The checkout contains the merged implementation as working-tree
changes, so these results apply to that exact tree rather than to a published tag.

## Completion traceability

| Requirement family | Canonical implementation | Final proof |
| --- | --- | --- |
| FR-PROJ / FR-SRC | Project, immutable source/version, secure URL/upload, documentation, credential APIs/services/repositories | Clean workflow created one project, ingested executable and documentation sources, then created a second immutable executable version |
| FR-NORM / FR-VEC / FR-AI | One canonical API model, provenance-preserving parsers, Milvus provider, bounded OpenRouter provider, typed enrichment/review | Initial and updated Builds completed parsing, indexing, enrichment, and validation; post-outage recovery required both Milvus and OpenRouter healthy before rebuilding |
| FR-COMP / FR-VAL / FR-BUILD | Deterministic compiler, `mcp-manifest/v1`, exact mappings, immutable Builds, 100% coverage gate, diff and secret-free export | Two READY Builds each had 100% coverage; source update added one operation; export contained exactly five expected files and no supplied secret material |
| FR-DEP | Compose base, durable deployment queue, Docker client/runtime manager, isolated dynamic containers, Traefik, stop/redeploy/rollback | Three real deployments reached edge-route readiness; replacement stopped the old runtime only after the exact candidate route was ready; rollback created a new deployment of the original immutable Build |
| FR-MCP | Official MCP SDK Streamable HTTP server, exact tools/resources, deterministic upstream executor | Real MCP clients listed 4 tools, then 5 after update, then 4 after rollback; documentation resource read and exact GET/POST/search mappings reached the HTTP fixture with the configured upstream authorization |
| FR-SEC | Local auth/RBAC/CSRF, encrypted credentials, separated inbound/outbound auth, SSRF/DNS policy, secret-safe runtime inputs | Bootstrap/login and CSRF mutations passed; token was disclosed once; runtime/environment/mount inspection found no builder/provider credentials, Docker socket, published ports, or writable secret mounts |
| FR-UI | Typed React application and ten-step lifecycle UI | Mock-backed cross-browser journeys passed; an additional opt-in Chromium test logged into the real Compose stack and observed the active rollback runtime |
| FR-OPS / NFR-009 | Audit, readiness maps, structured logs, service health, runbooks | Every long-running Compose service reports healthy; each RQ worker proves its own queue registration, Traefik uses private ping, and `runtime-init` exits zero as a one-shot gate |
| NFR-001/004/005/008 | Security, availability isolation, project isolation, resource bounds | Runtime continued serving while API, builder worker, Milvus, and OpenRouter fixture were down; live container hardening assertions all passed |
| NFR-002/003/006/007/010/011 | Reproducibility, determinism, performance, scale, upgradeability, testability | Frozen locks, generated-schema drift tests, deterministic fixture mappings, clean migration cycles, performance harnesses, unit/integration/Docker/E2E suites all passed |
| NFR-012/013/014/015 | Accessibility, browser support, privacy, no telemetry by default | Keyboard/security/compact-navigation journeys passed across supported browser projects; no chat/agent/telemetry path or secret redisplay was introduced |

No V2 route, duplicate model/service, compatibility layer, alternate persistence or
execution path, generated per-project application, canary, or shadow pipeline was added.

## Repository-controlled fixes completed in the final round

- Corrected PostgreSQL 18's versioned data-volume mount and made the Alembic path
  independent of the caller's working directory.
- Reused one local backend image across API/workers, made host-facing application ports
  configurable, and gave the one-shot initializer sole ownership of secure runtime-root
  preparation.
- Corrected CSV environment decoding, public read-schema boundaries, RQ-compatible job
  IDs, and Milvus immediate-read consistency.
- Upgraded and digest-pinned Traefik 3.7.11 for Docker Engine 29 compatibility.
- Added a real Traefik edge readiness probe. Activation now requires exact Build and
  Deployment IDs so provider propagation delay or an older same-Build runtime cannot
  satisfy replacement health.
- Made activation two-phase within the existing deployment state machine: the candidate
  remains `HEALTHCHECK/activating` while superseded resources retire, and only then is
  `RUNNING` plus its audit event committed. Worker retry resumes this same state instead
  of provisioning a parallel runtime.
- Kept production SSRF protection closed while allowing only explicitly configured
  development fixture hosts whose Docker DNS answer is private.
- Added Milvus, both RQ worker-registration, and private Traefik ping health checks. Base
  builder infrastructure remains on an internal network with no ineffective/stale host
  port promises.
- Applied Debian security upgrades in both Python images, removed the fixed OpenSSL
  finding, and purged unused `gzip`/`perl-base` runtime packages. This removed every
  CRITICAL image finding without suppressing the scanner.
- Added the deterministic full-stack harness and an opt-in Playwright test for the live
  Compose UI/API.

## Clean full-stack execution

Before the final run, the exact managed acceptance runtime and only the MCPlica Compose
project were removed, including its volumes. Compose created fresh networks/volumes,
the dedicated runtime bind root was verified empty, every long-running service became
healthy, and `runtime-init` exited `0`. Alembic upgraded an empty PostgreSQL database
through `0001 -> ... -> 0008`.

The final workflow passed this complete sequence:

```text
bootstrap/login -> project creation -> source ingestion -> canonicalization
-> documentation indexing -> AI enrichment -> build -> validation/coverage
-> artifact/export -> MCP access -> deployment -> MCP tool/resource calls
-> source update -> rebuild -> diff -> redeploy -> rollback
```

| Evidence | Final value |
| --- | --- |
| Project | `7b9a419e-d27d-4c4d-ab0c-f658cd43f15c` |
| Source versions | `599593cf-3d12-4593-b33c-a598624c9e74`, `a443be06-1cc6-417c-a7e3-6179d7fcb8c9` |
| Initial / updated Builds | `66e8dadb-2f4a-40d3-9d12-fb8dd310b636`, `ecdd76ec-bdf6-49e1-8668-532b429235b9` |
| Initial / replacement / rollback Deployments | `c7c261ab-afe5-4fe1-8d3b-d9a6b9da03d4`, `9359256c-36c1-4133-947e-0102824aa20a`, `b27efe58-c996-4227-8e13-c36c3ea29b64` |
| Coverage | 100% initial; 100% updated |
| Tool surface | 4 initial; 5 updated; 4 after rollback |
| Diff | 1 added operation |
| Documentation | 1 real MCP resource read |
| Export | `README.md`, `build-metadata.json`, `compose.example.yaml`, `manifest.json`, `validation-report.json` |
| First Build / deployment / MCP round trip | 5.181 s / 8.254 s / 0.168 s |
| Total workflow | 57.020 s |

During the workflow the OpenRouter fixture, API, builder worker, and Milvus were stopped.
The already-deployed MCP runtime still reached the upstream fixture. Recovery then had
to prove Milvus and OpenRouter healthy before the updated Build could start.
After the deterministic provider fixture shut down, the retained stack still reports
core readiness with `openrouter=false`, while the isolated rollback runtime continues to
report exact Build/Deployment readiness. This is the intended degraded-Builder boundary.

## Test and quality results

| Gate | Result |
| --- | --- |
| Backend + shared contracts | `82 passed, 1 skipped` in 4.20 s; the skip is the explicit opt-in real-Docker test |
| Real dynamic-Docker integration | `1 passed` in 30.82 s from the Linux worker boundary; two projects, isolated networks, same-Build replacement, rollback, exact route identity, cleanup |
| Full-stack lifecycle regression | Replacement and rollback each asserted the superseded row was already STOPPED, with `stopped_at <= started_at`, immediately when the candidate first reported RUNNING |
| Generic MCP runtime | `37 passed` in 2.45 s |
| Frontend unit | 4 files / 7 tests passed |
| Frontend quality/build | Prettier, ESLint, TypeScript, and production Vite build passed |
| Playwright isolated suite | 12 passed, 8 intentional project/viewport or opt-in-live skips in 31.0 s across Chromium, Firefox, WebKit, and mobile Chromium |
| Playwright live Compose | 1 Chromium test passed in 2.0 s: real login, project navigation, active healthy rollback runtime |
| Strict Python quality | Ruff and format clean across 253 files; project-scoped strict Pyright reports 0 errors/warnings for backend, tests, benchmarks, runtime, contracts, integration harness, and migration environment |
| Generated contracts | Committed manifest and API Inventory schemas equal the authoritative Pydantic schemas |
| Starter/lock/hygiene | 32 required files validated; uv lock resolved 102 packages; `git diff --check` and merge-marker sweep passed |

Migration validation also passed on a separate empty PostgreSQL database for full
`base -> 0008`, `0008 -> base`, and `base -> 0008` cycles. The final Compose run repeated
the empty-database upgrade and reports one `0008 (head)`.

## Performance-sensitive paths

These are reproducible local observations, not production latency promises.

| Harness | Result |
| --- | --- |
| 1,000-operation deterministic parse/compile/validate, 3 iterations | 4.950854 s median total; 856,581-byte manifest |
| Live Milvus 10,000 chunks, batch 256, 16 dimensions | 2.061168 s indexing; 17.722 ms median and 20.039 ms p95 across 20 project/generation-scoped searches; generated rows removed afterward |

## Security and runtime isolation

- `pnpm audit --audit-level high`: no known vulnerabilities.
- Frozen Python workspace `pip-audit`: no known vulnerabilities.
- Trivy 0.74.0 source vulnerability/misconfiguration/secret gate: exit 0 over the
  `.dockerignore`-filtered release tree; all three Dockerfiles report zero
  HIGH/CRITICAL misconfigurations.
- Final frontend `sha256:bc58a687...` has zero HIGH/CRITICAL image findings. Final
  backend `sha256:3852cc1d...` and runtime `sha256:44106c640...` each have zero
  CRITICAL and zero fixable HIGH findings. Each retains seven unfixed Debian 13 package
  findings (four unique advisories in ACL, ncurses, and SQLite); Trivy reports no fixed
  package version. The unused Perl/gzip removal reduced the original result from 16
  package findings, including 3 CRITICAL, to those 7 HIGH-only findings.
- Runtime secret directory/file modes are `0700` / `0600`, owned by `10001:10001`.
- The active rollback runtime is healthy as `10001:10001`, read-only, unprivileged,
  `cap_drop=ALL`, `no-new-privileges`, 512 MiB, 1 CPU, 256 PIDs, hardened 64 MiB
  tmpfs, and bounded 10 MiB x 3 logs.
- It has exactly one project network, no host port, no Docker socket, and only two
  read-only bind mounts (manifest and typed secret bundle). Its environment has no
  OpenRouter, Milvus, PostgreSQL, Redis, database, bootstrap, encryption, or Docker
  credential variable.
- `/readyz` and the Traefik edge route report the exact rollback Build
  `66e8dadb-2f4a-40d3-9d12-fb8dd310b636` and Deployment
  `b27efe58-c996-4227-8e13-c36c3ea29b64`.
- Database timestamps prove terminal ordering: the first runtime stopped at
  `15:25:42.435736Z` before its replacement became RUNNING at `15:25:42.450452Z`,
  and the replacement stopped at `15:25:50.746070Z` before rollback became RUNNING at
  `15:25:50.760860Z`.
- The Docker socket exists only on the deployment worker and Traefik. The builder
  network is internal; Traefik alone joins the active project's route network.

## External promotion gates

No repository-controlled blocker remains in the requested scope. The following cannot
be certified by a local checkout without operator-owned systems or credentials:

- publication of upstream Debian fixes for the seven HIGH-only base-package findings,
  or a target-owner risk acceptance while those fixes remain unavailable;
- real OpenRouter account/model availability, quota, pricing, and production responses;
  the final workflow used a deterministic OpenRouter-compatible HTTP fixture and did not
  receive or persist a real provider key;
- production DNS, certificates/ACME, firewall, hardened Linux host, external secret
  manager, immutable registry publication/signing/SBOM retention, and hosted CI/security
  required-check evidence;
- target backup/restore, monitoring/alert delivery, disaster-recovery, and live upgrade
  drills;
- organization controls such as private security reporting, CLA/branch protection, and
  sponsor-platform publication.

**Final status:** repository implementation and local functional/production-safety
acceptance are complete. MCPlica is ready for controlled target-environment promotion
once the upstream-unfixed image findings are patched or explicitly risk-accepted and the
operator-owned gates above are executed. It is not claimed as already deployed or
externally certified.
