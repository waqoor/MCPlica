# MCPlica Customer Workflow — QA Testing Plan

**Prepared for:** QA lead / engineering management review, prior to execution
**Scope owner:** Customer-facing "API → MCP" workflow QA
**Environment under test:** Local Docker Compose install, `http://localhost:8081` (UI) / `http://localhost:8000` (API), commit at time of writing on `master`, working tree clean
**Status:** Plan complete. Initial P0 execution has begun — see `QA_SUMMARY.md` for current pass/fail/blocked counts.

---

## 1. Objective

MCPlica's entire value proposition is a single promise: **give it your OpenAPI spec, and it will produce an MCP server that behaves exactly like your API — no more, no less.** A customer who imports their API is trusting MCPlica to preserve HTTP method, path, parameters, types, and authentication *exactly*, while only using AI to make the result easier to understand (titles, descriptions, categorization).

What is being tested:
- The full customer journey from first login through a working, callable MCP tool: authenticate → create a project → import an API spec → (AI analysis) → generate an MCP manifest → validate/build → configure credentials and inbound MCP access → deploy an isolated runtime → call a tool → see it reach the real upstream API.
- The negative, boundary, security, and recovery paths around that journey (invalid specs, missing credentials, RBAC, cross-project isolation, build/deploy failure handling).

Why it matters: this product sits directly in a company's request path to its own APIs. Two failure classes are unacceptable and correspond to the two things QA must prove don't happen:
1. **Silent fidelity loss** — the generated tool calls a different method, path, or parameter set than the source API. This is invisible to the customer until it causes an incident against a real upstream system (wrong endpoint hit, required field dropped, wrong data type sent).
2. **Silent isolation loss** — one project's credentials, data, or MCP runtime become reachable from another project, or an unauthenticated caller reaches a tool endpoint.

A successful customer journey means: the customer never has to manually verify that MCPlica "got the API right" — the platform's own deterministic validation (see §4, stage 7) already proved it before the customer could deploy. QA's job is to verify that guarantee actually holds, and that every point where it *could* fail (AI enrichment, compilation, build validation, deployment) fails **loudly and safely** rather than silently.

This is why API → MCP correctness (§Phase 5, `AI-*` test IDs) is treated as the single highest-value area in this plan, ahead of general CRUD/UX coverage.

---

## 2. Scope

### In scope

Everything required for a self-hosted operator (the "customer" in this plan — MCPlica is self-hosted with no SaaS/multi-tenant model, per README §"Non-negotiable boundaries") to:
- Reach and authenticate to MCPlica (cookie session, CSRF, role-based access: `ADMIN` / `BUILDER`).
- Create a project (`PROJECT-*`).
- Import an OpenAPI specification (upload or URL), including versioning/dedup behavior (`IMPORT-*`).
- Have the spec deterministically parsed, with invalid input surfaced as actionable findings (`IMPORT-*`, `BUILD-*`).
- Have AI analysis enrich operation semantics only, never HTTP behavior (`AI-*` — the Phase 5 focus area).
- Have a deterministic MCP manifest/tool set compiled and independently re-validated (`AI-*`, `BUILD-*`).
- Bind upstream credentials to detected security schemes (`CRED-*`, folded into `BUILD-*`/`DEPLOY-*` below).
- Configure inbound MCP access (static bearer or OAuth/OIDC) (`MCP-*`).
- Deploy an isolated per-project MCP runtime and roll back/redeploy (`DEPLOY-*`).
- Connect an MCP client, list tools, and call a tool through to the real upstream API (`MCP-*`).
- Negative, boundary, and recovery paths for every stage above (invalid specs, missing config, build/deploy failure, upstream errors, refresh-mid-operation).
- Security/isolation: authentication, CSRF, RBAC enforced server-side, credential secrecy, cross-project runtime/network isolation, MCP inbound auth (`SEC-*`).
- UX: wizard step gating/remediation messaging, progress visibility during long-running builds/deploys, error message clarity (`UX-*`).

### Out of scope

Excluded only where the repository itself places it outside this workflow:
- **Production Compose overlay / TLS / DNS / ACME** (`infra/compose.production.yaml`, `docs/operations/domain-tls.md`) — this plan targets the local development stack the README documents; production hardening has its own documented, separate procedure and is not part of the customer *workflow*.
- **The repository's own disposable acceptance harness** (`tests/integration/full_stack_workflow.py`) — its own README explicitly restricts it to a fresh, disposable install because it stops/recreates services and mutates settings; running it against our persistent local install would violate this engagement's hard rule against resetting the environment. Its scope overlaps this plan's P0/P1 workflow tests and is noted as a **regression-phase** asset, not something QA re-implements from scratch.
- **CI/release automation, SBOM/signing, dependency scanning** (`docs/maintainers/`) — supply-chain concerns with their own release-gate process, not part of the customer-facing journey.
- **Backend/frontend/mcp_runtime unit test suites** (`backend/tests/`, `mcp_runtime/tests/`, `frontend/src/**/*.test.tsx`) — already extensive, already covering compiler/validator/runtime-security logic at the unit level (see fixtures README for the specific overlap). This plan's `AI-*` tests target **end-to-end, black-box** verification of the same guarantees, not duplication of existing unit coverage.
- **Multi-tenant/cross-customer SaaS isolation** — not applicable; MCPlica is explicitly single-install/self-hosted. "Isolation" in this plan means *project*-level isolation within one install (credentials, runtime, network), not tenant isolation between different companies' installs.

---

## 3. Test strategy

| Strategy | Why it matters for MCPlica |
|---|---|
| **Functional / happy-path** | Proves the core promise works at all: a real spec becomes a real, callable tool. Every other test type is only meaningful once this baseline is established. |
| **Negative testing** | MCPlica's own architecture rule is "fail closed, never guess" (missing credentials, unsupported schemas, unresolved refs must block, not degrade). Negative tests are how QA verifies the platform actually fails closed rather than silently producing a broken or incomplete tool. |
| **Boundary testing** | Size limits (manifest size, upload size, document size), coverage thresholds (100% operation coverage required), and pagination/retry limits are explicit, numeric, documented constraints — the kind of logic most likely to have off-by-one defects. |
| **Integration testing** | The workflow crosses 6+ services (Postgres, Redis, Milvus, OpenRouter, Docker, Traefik) and 2 async workers. Most real defects in a system like this live at integration seams (e.g., a build stuck because a worker never picked up a queued job), not inside any single function. |
| **AI/MCP generation correctness** | The single highest-value area (see §1). AI must be able to enrich semantics without ever being able to alter executable HTTP behavior — this is claimed as an architectural, type-level guarantee (AI only ever writes `operation.semantic`) and QA must verify it holds under adversarial/confusing input, not just typical input. |
| **Security/isolation testing** | A deployed MCP runtime executes real HTTP calls against real upstream systems using real credentials. RBAC, CSRF, credential secrecy, and per-project network isolation are the controls standing between "internal tool" and "incident." |
| **Error recovery** | Long-running async operations (builds, deployments) are exactly the operations most likely to be interrupted by a page refresh, a worker crash, or a cancellation request. The platform's stated design (durable per-stage state, resumable pipeline, cooperative cancellation) is a testable claim, not just an assumption. |
| **Regression testing** | Once OpenRouter is configured and the full pipeline becomes executable, every test blocked in this initial round must be re-run — plus a full pass after any bug fix, using the existing `tests/integration/full_stack_workflow.py` harness on a disposable install as a complementary, deeper check. |
| **UX testing** | The 10-step wizard's own step-gating (`GET /projects/{id}/journey`) is customer-facing product logic with reason codes and remediation text — its accuracy directly determines whether a real customer understands what to do next. |

---

## 4. Actual customer workflow

Derived from the live API (`openapi.json`), `frontend/src/features/projects/wizard-steps.ts` (confirmed 10-step wizard), and cross-checked against `docs/user-guide.md`. Only stages that actually exist in the implementation are listed.

| # | Stage | Customer action | System behavior | Backend/API | State transition | Expected result | Dependencies |
|---|---|---|---|---|---|---|---|
| 0 | Auth | Log in with email/password | Cookie session issued (`mcplica_access`, `mcplica_refresh` HttpOnly; `mcplica_csrf` readable) | `POST /api/v1/auth/login` | Session row created | `200`, user/role returned | PostgreSQL |
| 1 | Project identity | Name, slug, description | Project record created; slug fixes the future MCP hostname (`<slug>.<mcp-domain>`) | `POST /api/v1/projects` | New `projects` row | `201`, `mcp_hostname` returned | none |
| 2 | Executable source | Upload OpenAPI file or register a URL | File/URL stored as an **immutable version**; content-hash deduplicated; **not parsed yet** | `POST /projects/{id}/sources/upload` or `/sources/url` | New `sources`+`source_versions` rows | `201` regardless of spec validity — validation is deferred | none for upload; secure-fetch policy for URL sources |
| 3 | Documentation (optional) | Upload supporting docs | Chunked/indexed for AI context only; cannot define executable behavior | `POST /projects/{id}/sources/upload` (`kind=documentation`) | New source rows | `201` | Milvus, OpenRouter embeddings |
| 4 | API server | Confirm detected base URL(s) | Resolves server variables/ambiguity | (part of project/source config) | `server_mappings` set | Explicit server binding recorded | none |
| 5 | Upstream authentication | Bind a credential per detected security scheme | Credential encrypted at rest (AES-256-GCM); scheme/name/location bound | `POST /projects/{id}/credentials` (admin only) | New `credentials` row | `journey` step 5 → `complete` | none |
| 6 | Start build | Click "Build" | **Pre-flight check**: rejects immediately if AI models aren't configured (confirmed live, see §Phase 7) | `POST /projects/{id}/builds` | `builds` row `QUEUED` → pipeline | `202`/build id, **or `409 INVALID_STATE` if models unconfigured** | Redis/RQ (queue), then per-stage: Milvus (`INDEXING`), OpenRouter (`ANALYZING`) |
| 7 | Build progress | Watch live progress | Worker advances `QUEUED→INGESTING→PARSING→INDEXING→ANALYZING→COMPILING→VALIDATING→PACKAGING→READY` (or `FAILED`/`CANCELLED`) | `GET /builds/{id}/events` (SSE), `GET /builds/{id}` | Durable per-stage state | Build reaches `READY` or a specific, findable `FAILED` reason | builder-worker, OpenRouter, Milvus |
| 8 | Validation | Review coverage/findings | 8-layer deterministic validation, incl. re-running the manifest in the real runtime factory | `GET /builds/{id}/validation` | Validation report attached to build | 100% expected-operation coverage, zero blocking findings before `READY` | Docker (validation harness) |
| 9 | MCP access | Choose static bearer or OAuth/OIDC | Bearer shown once, stored as digest only | `PUT /mcp-access/auth-mode`, `POST /mcp-access/tokens` | `journey` step 9 → `complete` | Auth config `effective` | none |
| 10 | Deploy | Select the READY build, confirm | Synchronous preflight, then async: isolated Docker network + container, Traefik routing, health verification | `POST /projects/{id}/deployments` | `deployments` row → `HEALTHCHECK` → `active` | Deployment `active`, old healthy deployment never silently replaced by an unhealthy one | Docker Engine, Traefik, deployment-worker |
| 11 | MCP client connection | Configure client with `https://<slug>.<mcp-domain>/mcp` + bearer token | Runtime validates inbound auth, serves manifest-derived tools | `mcp_runtime` `/mcp` (Streamable HTTP) | n/a (stateless) | `initialize`/`tools/list` succeed, schemas match the validation report exactly | none — runtime has **zero** OpenRouter/Milvus dependency at call time |
| 12 | Tool call | Invoke a tool | Validate args → deterministic request builder → allowlisted-host HTTP call → real upstream API → mapped MCP result | `mcp_runtime` `/mcp` `tools/call` | n/a | Correct upstream call, structured/error result, no HITL gate | Real upstream API |

---

## 5. Test phases

Time estimates are derived directly from the test-case count and type in `GOOGLE_SHEETS_TEST_CASES.csv` (see basis note below the table), not arbitrary figures.

| Phase | Objective | Key Coverage | Priority | Execution Time | Setup Time | Buffer | Deliverable |
|---|---|---|---|---:|---:|---:|---|
| 1. Auth & Access Control | Prove session, CSRF, and role enforcement hold under real requests, not just UI hiding | `AUTH-001..010` | P0/Security | 1.5h | 0.25h | 0.25h | Executed AUTH rows in CSV |
| 2. Project Lifecycle | Prove project CRUD, journey gating, async deletion behave as documented | `PROJECT-001..008` | P0/P1 | 1h | 0.1h | 0.15h | Executed PROJECT rows |
| 3. API Source Import & Parsing | Prove upload/versioning/dedup works and invalid specs are caught (at build-parse time, not upload time) | `IMPORT-001..013` | P0/P1 | 2h | 0.5h (fixtures already built) | 0.3h | Executed IMPORT rows |
| 4. AI Analysis & API→MCP Correctness | **Highest-value phase.** Prove AI enrichment cannot alter HTTP behavior; verify method/path/param/type/auth fidelity end to end | `AI-001..018` | P0/P1/P2 | 4h | 0.5h (OpenRouter key + models) | 0.5h | Executed AI rows, fixture-based evidence |
| 5. Build Pipeline & Validation | Prove the 9-state build machine, cancellation, retries, and the deterministic validator's hard-fail checks | `BUILD-001..011` | P0/P1 | 2.5h | 0.25h | 0.25h | Executed BUILD rows |
| 6. Credentials & Deployment | Prove credential scheme enforcement, deploy preflight, isolation, rollback | `DEPLOY-001..013` | P0/P1 | 3h | 0.5h (Docker access) | 0.3h | Executed DEPLOY rows |
| 7. MCP Runtime & Tool Execution | Prove `tools/list`/`tools/call` reach the real upstream correctly, and inbound auth is enforced | `MCP-001..011` | P0/P1 | 2.5h | 0.25h (real/mock upstream) | 0.25h | Executed MCP rows |
| 8. Security & Isolation | RBAC, IDOR, credential exposure, cross-project isolation, MCP auth | `SEC-001..011` | Security | 2h | 0.25h (2nd test user) | 0.25h | Executed SEC rows |
| 9. UX & Error Recovery | Wizard gating accuracy, refresh-mid-build, partial-failure recovery, error message clarity | `UX-001..008` | P1/P2 | 1.5h | 0.1h | 0.15h | Executed UX rows |
| 10. Regression Pass | Re-run every previously blocked/failed case after OpenRouter is configured and/or fixes land; run `tests/integration/full_stack_workflow.py` on a **disposable** clone as a deeper cross-check | All blocked cases + fixed bugs | P0/P1 | ~8h (full suite) | 1h (disposable clone + config) | 1h | Regression report, updated CSV |

**Basis for the estimate:** ~105 test cases total (see `GOOGLE_SHEETS_TEST_CASES.csv`), averaging ~12 minutes execution per functional/API-level case and ~20-25 minutes per case requiring a full build→deploy→call round-trip (Phases 4-7), which is the dominant cost driver since a single build can take several minutes end to end. Phases 1-3 and 8-9 are mostly single-request API/UI checks (fast); Phases 4-7 are pipeline-dependent (slow, and currently blocked — see §8).

- **Total estimated execution time:** ~20.5h
- **Total estimated setup/data-prep time:** ~3.7h (mostly one-time: fixture authoring — already complete — OpenRouter configuration, second test user, Docker access)
- **Reasonable buffer (~15%):** ~3.4h
- **Total estimated QA effort:** **~27.5h**, of which **~19h (Phases 4-7 + regression) cannot proceed until `OPENROUTER_API_KEY` and analysis/validation/embedding models are configured** (see §6, §8).

---

## 6. Entry criteria

Only what MCPlica actually requires, confirmed against the live install:

- [x] Application stack running and healthy — confirmed: `GET /api/v1/health` → `{"status":"ok"}`, all 11 Compose services `healthy`, `migrate`/`runtime-init` exited `0`.
- [x] Admin account available — confirmed via `python scripts/init_env.py` + `ensure_development_admin`.
- [x] Test API specifications available — `qa/customer-workflow/fixtures/*.yaml` (this plan's Phase 6 deliverable), built specifically for the test cases that use them.
- [x] Docker available for the operator machine — confirmed (Docker Desktop 4.87.0, Compose v5.4.0).
- [ ] **`OPENROUTER_API_KEY` configured, plus `analysis_model` / `validation_model` / `embedding_model` chosen** (via `.env` or `PUT /api/v1/settings/openrouter` + `PUT /api/v1/settings/models` after login) — **currently NOT met**. Confirmed live: `GET /api/v1/ready` reports `"openrouter": false`, and `POST /projects/{id}/builds` returns `409 INVALID_STATE: "Build models are not configured: analysis_model, validation_model, embedding_model"`. This blocks Phases 4-7 and the regression pass entirely (see §8, Risk 1).
- [ ] A second, real, reachable upstream test API — needed only for Phase 7 end-to-end `tools/call` execution against a live upstream (a local mock/echo service is an acceptable substitute and should be prepared before Phase 7 begins).
- [x] A non-admin (`BUILDER`) test account for RBAC testing — created during this round (`qa-builder-tester@example.com`).

## 7. Exit criteria

- All P0 test cases either executed with a recorded result, or explicitly `BLOCKED` with a named, still-open dependency (never silently skipped).
- The fundamental customer workflow (project → source → build → deploy → tool call) validated end to end **at least once** with a real OpenRouter key.
- All confirmed Critical/Blocker defects in `BUGS_FOUND.csv` are either fixed and re-verified, or formally accepted/deferred by the product owner in writing.
- P1 coverage completed for every stage that P0 exercised.
- A full regression pass (Phase 10) completed after OpenRouter configuration and after any bug fixes.
- Every `BLOCKED` case has a one-line reason a non-technical stakeholder can understand ("requires OpenRouter API key" is acceptable; "environment issue" is not).
- `QA_SUMMARY.md` reflects final, not interim, counts.

## 8. Risks and dependencies

| # | Risk | Impact | Status / mitigation |
|---|---|---|---|
| 1 | **`OPENROUTER_API_KEY` not configured** | Blocks Phases 4-7 entirely (build cannot even be *queued*, confirmed live — not merely "AI stage degraded"). This is the single largest blocker in this round. | Documented, reproducible, not a bug (matches design_document.md §13.1's stated rule). Needs a real key + model choice from the product owner; QA cannot and will not fabricate one. |
| 2 | **AI nondeterminism** | Even with a key, AI-authored `title`/`description`/`category` text is not byte-reproducible run to run, which affects any test asserting exact semantic text. | Mitigate by asserting *structural* invariants (method/path/params unchanged, `operation_key` correctly attributed) rather than exact wording — this is what `AI-*` test cases are designed around. |
| 3 | **Milvus dependency for indexing/documentation-driven enrichment** | `INDEXING` stage and documentation-context retrieval depend on Milvus; currently `healthy` and reachable, low residual risk, but a real dependency nonetheless. | Confirmed `milvus: true` in readiness; monitor during Phase 4 execution. |
| 4 | **Docker/runtime deployment complexity** | Deployment tests create real containers/networks; a misconfigured host Docker (network conflicts, resource limits for Milvus's 8g default) can produce environment failures that look like product bugs. | Already hit once during initial setup (host port conflict, resolved via `.env` port reassignment, not a product defect) — testers must distinguish environment issues from product defects before filing a bug. |
| 5 | **Long-running operations** | Builds/deployments are multi-minute async operations; SSE-based progress and cancellation are real behaviors to verify, not assumptions. | Covered explicitly in `UX-*` (refresh-mid-build) and `BUILD-*` (cancellation) cases. |
| 6 | **No real upstream test API by default** | Phase 7 `tools/call` tests need something to actually call. | Prepare a small local mock/echo HTTP service before Phase 7 (out of scope for this plan's fixture set, which only covers the *source spec* side). |
| 7 | **Worker/queue failures are hard to distinguish from product bugs without log access** | `builder-worker`/`deployment-worker` failures may originate in infra (Redis, Docker socket permissions) rather than product logic. | Testers must check `docker compose logs api builder-worker deployment-worker` before filing a build/deploy bug (per README §5). |
| 8 | **Repository's own disposable acceptance harness cannot be run here** | `tests/integration/full_stack_workflow.py` covers much of this same ground but requires a fresh, disposable install — running it against our persistent local install would violate the "no reset" hard rule for this engagement. | Scheduled as a **separate, explicitly disposable** exercise in Phase 10, not folded into this plan's execution against the current install. |

---

## Negative source-fixture catalog (supplement to `fixtures/invalid-api.yaml`)

To keep the fixture set at exactly four files, `invalid-api.yaml` isolates one clean defect (duplicate `operationId`, confirmed hard-fail at `backend/app/parsers/openapi/parser.py:1072`). The other documented invalid-input classes are covered by minimal, tester-authored edits of that same file, referenced by the `IMPORT-*`/`BUILD-*` test cases that need them:

| Defect | Minimal edit to `invalid-api.yaml` | Expected result |
|---|---|---|
| Missing `info.title` | Delete the `title:` line under `info` | Build `PARSING` stage hard-fails; `info.title` required |
| Unresolved/malformed `$ref` | Add a property `$ref: "#/components/schemas/DoesNotExist"` | Build `PARSING` stage hard-fails on the dangling reference |
| Relative server URL without a project default | Change `servers[0].url` to `/v1` and leave the project's `default_base_url` unset | Build `PARSING` stage hard-fails (relative server requires a configured default base URL) |
| Non-OpenAPI document | Replace `openapi: 3.1.0` with `swagger: "2.0"` | Build `PARSING` stage hard-fails (only 3.0.x/3.1.x accepted) |
| Unsupported cookie parameter | See `fixtures/complex-api.yaml` operation `exportOrders` — already included, no edit needed | `COMPILING` stage hard-fails |
| Unsupported request-body media type | See `fixtures/complex-api.yaml` operation `generateShippingLabel` — already included, no edit needed | `COMPILING` stage hard-fails |

---

## Glossary note (documentation ambiguity, flagged not resolved)

`docs/api-inventory-v1.md` (the MCPlica **control-plane REST route inventory**) and the `api-inventory/v1` **source input format** (an alternative to OpenAPI for describing a customer's API, `design_document.md` §9) share the same version-style name for two unrelated concepts. Testers should read "API Inventory" in a test case as the *source format* unless a case explicitly says "route inventory."
