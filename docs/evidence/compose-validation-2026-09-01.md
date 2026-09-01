# Compose re-validation: 2026-09-01

## Scope and evidence identity

This round starts from `2ad6d42efd807553a8bb60757541eaea330f6771` and is tracked in
GitHub PR #20 (`fix/compose-e2e-validation-20260901`). The PR's CI job and artifacts,
bound to their recorded commit SHA, are the source of post-fix execution results.
Test code being present is not proof that a run passed. The final PR summary records
actual results and any unresolved external prerequisite.

Local regression execution proved nine focused fixture/configuration checks. Local
Python parsing found no syntax errors in tracked Python sources. This session has no
Docker daemon; actual multi-container validation runs on the GitHub-hosted Docker
runner, not on an invented local installation.

## Verified code snapshot

Code commit: `742d649b79db240d2c32087935a5c1cb0628f47c`.
CI run: `33516768996`. Subsequent documentation-only commits do not change the
application, configuration, tests, or CI definitions verified by this run.

Backend, runtime, frontend, and cross-browser jobs passed, including formatting,
lint, type checks, PostgreSQL migrations, schema-drift detection, critical-module
coverage checks, API contracts, assets, and the frontend production build. The
mock-backed browser report records 16 passed, zero failed/flaky, and eight explicit
skips (four live-stack opt-ins and four browser/device-specific exclusions).

Resolved production Settings validation passed for all four control-plane
processes. All three canonical application images built. All 13 Compose services
reached their required startup states. The full-stack workflow passed, including
builder/provider outage recovery, changed-source rebuild, replacement, rollback,
and persisted state plus authenticated MCP execution after container recreation.

The Docker job completed successfully, including the separate two-project runtime
isolation/replacement/rollback test. The live Chromium report records one passed,
zero failed, and zero skipped tests. Final service evidence confirms 11 healthy
running services and both one-shot services exited 0. The source-to-runtime workflow
completed in 80.434 seconds, with four initial tools, five after rebuilding, and four
after rollback; generated-operation coverage was 100% for both fixture builds. This
is operation coverage for that fixture, not repository line coverage.

Security run `33516768853` passed secret scanning, locked dependency audits, and
repository scanning. CI run `33516768996` remains overall **failed** solely because
its separate dependency-review job is unsupported for this repository; the five
application/acceptance jobs all passed. The existing CLA integration is not completed
by this PR.

The downloaded `compose-validation` artifact is `9804352103`; its SHA-256 is
`961f8e6d80b413a6a2a942e5fedf6f2eebb71a1875f3b851eb85d1ffe6e2b499`.
The artifact hash was verified before reading the report. Permanent non-secret
extracts are retained in `compose-2026-09-01/workflow.json`, `services.json`, and
`validation-summary.json`. The runner removed its disposable containers and volumes
after collecting evidence; no production server was changed or left running.

## Reproduced baseline failure

CI run `33509201508` built all three application images and brought all 13 services
to their required startup states. The first Build and deployment succeeded. During
the intentional builder/provider outage exercise, restarting the OpenRouter fixture
failed with `OSError: [Errno 98] Address already in use` on port 9010. This stopped
subsequent rebuild/rollback/live-browser validation. Initial startup success must
not be reported as full end-to-end success.

## Corrections and verification boundaries

- Owned reusable fixture sockets; bounded startup/shutdown, cancellation cleanup,
  and regression coverage for actual TIME_WAIT restart and unrelated occupied ports.
- Consistent database, queue, mount, runtime-image, and edge inputs across all
  control-plane processes, with no application secrets passed to runtime-init.
- Consistent production settings for migrations/API/workers, explicit replacement
  of development edge listeners, and validation using actual resolved Compose JSON
  plus the application's Settings model.
- Frozen development installations, consistent alternate environment-file handling,
  explicit non-production acceptance opt-in, and final service-health verification.
- Real post-rollback container recreation with named volumes retained; persisted
  active references and an authenticated MCP call are checked afterwards.
- Least-privilege PR-read permission for secret scanning, with PR comments disabled
  rather than granting a scanning job write access.

The run exercises the existing architecture. It does not add an alternate runtime,
compatibility layer, generated per-project application, shadow/canary path, or test
execution during ordinary application deployment.

## CI interpretation

The `backend`, `runtime`, `frontend`, `e2e`, and `docker` jobs must each be inspected.
The Docker job includes both actual runtime-isolation acceptance and the live browser
check. Its `compose-validation` artifact contains workflow outcomes, service states,
and diagnostics. A mock-backed browser pass is distinct from the live browser pass.

A GitHub dependency-review run returned "Dependency review is not supported on this
repository"; dependency graph/security-feature prerequisites are repository settings.
That check is retained and must not be represented as passing or disabled to obtain a
green badge. The separate locked Python/pnpm audits and repository scan are distinct
checks and do not silently substitute for an unavailable dependency-review result.

The pre-existing CLA workflow is also a fail-closed placeholder requiring the
repository's approved verification service. This PR does not remove that policy or
change paid security features, repository visibility, branch protections, or merge
requirements.

## Not established by this round

No production server or real provider credentials were supplied. Live OpenRouter
model behavior, release-image publication/signatures, public DNS, ACME certificate
issuance, hardened-host capacity, a production rollout, and encrypted backup/restore
remain separately verifiable operations. Synthetic production configuration validates
settings and failure behavior only; it neither pulls fake digests nor requests real
certificates. See `../release/release-checklist.md` for release prerequisites.

Earlier dated records in `final-integrated-validation.md` and `issues-001-closure.md`
are historical evidence for their stated snapshots, not proof of this PR's result.

The earlier `issues_002.md` inventory is pinned to an older baseline. This Compose
round does not reclassify or assert closure of all 55 findings, nor claim that
every possible feature path or failure mode was exercised.
