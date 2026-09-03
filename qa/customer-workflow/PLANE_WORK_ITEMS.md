# Plane QA Work Items — MCPlica Customer Workflow

**No Plane integration/tooling was available in this environment** (checked
via tool search; none found). These work items were **not** created
directly in Plane. They are written below ready to be copied into Plane
as-is — one work item per section, each mapping to a meaningful QA phase
rather than to individual test cases.

---

## 1. Repository & Workflow Analysis

**Description:** Read MCPlica's product/architecture documentation
(README, user-guide, mcp-client-connection, product_requirements,
design_document, architecture, implementation_plan) and trace the actual
implementation (backend API routers, compiler, validators, deployment
services, mcp_runtime, frontend wizard) to establish ground truth for the
customer workflow before any test is written.

**Objective:** Produce a verified, implementation-grounded understanding of
the real 10-step customer workflow, the exact API surface, the AI/HTTP
fidelity guarantees, and every point where documentation and implementation
might diverge.

**Scope:** All `docs/*` files listed in the QA brief; `backend/app/api`,
`backend/app/compilers`, `backend/app/validators`, `backend/app/services`,
`mcp_runtime/app`, `frontend/src/features/projects`, `openapi.json`.

**Key test coverage:** N/A (research phase; informs all test IDs).

**Dependencies:** None (read-only, local repo).

**Priority:** P0 (blocking — everything else depends on this being right).

**Estimated effort:** ~3h (already completed).

**Acceptance / completion criteria:**
- Documented workflow and implementation cross-checked, discrepancies flagged (not silently resolved).
- Exact REST API surface confirmed against `openapi.json` (ground truth), not assumed from docs.

**Deliverables:** Findings folded directly into `TESTING_PLAN.md` §4 (workflow table) and the fixture design rationale in `fixtures/README.md`. No standalone research document produced (per instructions, work directly into the plan).

---

## 2. Test Planning & Test Case Design

**Description:** Translate the verified workflow into a professional test
plan, a full test-case matrix, and four purpose-built OpenAPI fixtures.

**Objective:** A test plan and case set that a QA lead could hand to a team
and get consistent execution, with every case traceable to a real
implementation detail (file/line where relevant) rather than a generic
template.

**Scope:** `TESTING_PLAN.md`, `GOOGLE_SHEETS_TEST_CASES.csv` (103 cases),
`fixtures/*.yaml` + `fixtures/README.md`.

**Key test coverage:** N/A (planning phase; produces all test IDs `AUTH-001` through `UX-008`).

**Dependencies:** Work item 1 (analysis).

**Priority:** P0.

**Estimated effort:** ~6h (already completed).

**Acceptance / completion criteria:**
- Every test case has a clear, checkable expected result (Pass/Fail/Blocked decidable).
- Test count is derived from real feature complexity, not padded (103 cases, weighted toward the AI/MCP-correctness area per its actual risk).
- All 4 fixtures documented with purpose + test-ID cross-reference.

**Deliverables:** `TESTING_PLAN.md`, `GOOGLE_SHEETS_TEST_CASES.csv`, `fixtures/` directory.

---

## 3. Authentication & Access Control QA

**Description:** Execute and verify the login/session/CSRF/RBAC surface
against the running application.

**Objective:** Prove session and role enforcement hold under real requests
server-side, not merely hidden in the UI.

**Scope:** `POST /auth/login`, `/logout`, `/refresh`, `GET /auth/me`, CSRF
enforcement on mutating endpoints, cookie attributes.

**Key test coverage:** `AUTH-001` through `AUTH-010`.

**Dependencies:** Running application; admin account (already available).

**Priority:** P0.

**Estimated effort:** 1.5h execution + 0.25h setup (see `TESTING_PLAN.md` §5).

**Acceptance / completion criteria:**
- All P0 AUTH cases executed with a recorded result.
- Any FAIL has a filed bug entry (**already true**: `AUTH-007` → `BUG-001`).

**Deliverables:** Executed `AUTH-*` rows in the CSV (9 of 10 executed this round; `AUTH-009` refresh-rotation and `AUTH-010` bearer/CSRF-bypass remain).

**Status this round:** 8 PASS, 1 FAIL (`BUG-001`), 1 BLOCKED, 1 not yet attempted.

---

## 4. Project Lifecycle QA

**Description:** Verify project CRUD and the wizard's step-gating (`journey`) endpoint against real project state.

**Objective:** Prove project creation/retrieval/update/deletion behave as documented, and that the customer-facing wizard gating is accurate (not cosmetic).

**Scope:** `POST/GET/PATCH/DELETE /projects`, `GET /projects/{id}/journey`.

**Key test coverage:** `PROJECT-001` through `PROJECT-008`.

**Dependencies:** Work item 3 (needs an authenticated session).

**Priority:** P0/P1.

**Estimated effort:** 1h execution + 0.1h setup.

**Acceptance / completion criteria:** All P0/P1 PROJECT cases executed; async deletion behavior (`PROJECT-007`) specifically verified end to end (poll until cleanup completes), not just the initial 202.

**Deliverables:** Executed `PROJECT-*` rows.

**Status this round:** 3 PASS (`PROJECT-001`, `PROJECT-003`, `PROJECT-008`), 5 not yet attempted.

---

## 5. API Source Import & Parsing QA

**Description:** Verify spec upload, versioning/dedup, and — critically —
that invalid input is deferred to build-time parsing rather than rejected
synchronously at upload (a real, confirmed behavior, not an assumption).

**Objective:** Prove the import surface handles valid and invalid OpenAPI
input exactly as the implementation actually behaves.

**Scope:** `/sources/upload`, `/sources/url`, `/sources/{id}/versions`, `/sources/{id}/refresh`.

**Key test coverage:** `IMPORT-001` through `IMPORT-013`.

**Dependencies:** Work item 4 (a project to import into); `fixtures/simple-api.yaml`, `fixtures/invalid-api.yaml`, `fixtures/complex-api.yaml`.

**Priority:** P0/P1.

**Estimated effort:** 2h execution + 0.5h setup (fixtures already built).

**Acceptance / completion criteria:** Upload-time behavior (deferred validation) confirmed; build-time PARSING-stage rejection confirmed for each negative-fixture-catalog variant once OpenRouter is configured (currently blocked, see work item 6's dependency note).

**Deliverables:** Executed `IMPORT-*` rows.

**Status this round:** 2 PASS (`IMPORT-001`, `IMPORT-002`), 5 BLOCKED (all require a build, which requires OpenRouter), 6 not yet attempted.

---

## 6. AI Analysis & API→MCP Correctness QA

**Description:** The single highest-value QA area (see `TESTING_PLAN.md`
§1). Verify, end to end, that AI enrichment can improve semantics but can
never alter HTTP method/path/parameters/body/auth — using both a
structurally complex fixture and a fixture specifically designed to
confuse AI naming/attribution.

**Objective:** Prove the platform's core promise: "what you import is what
gets called," under both normal and adversarial-naming conditions.

**Scope:** AI analysis stage, MCP manifest compilation, deterministic build
validator's hard-fail checks (method/path/param/auth-changed detectors).

**Key test coverage:** `AI-001` through `AI-018`.

**Dependencies:** **`OPENROUTER_API_KEY` + analysis/validation/embedding
models configured — currently NOT met.** Confirmed live: `POST
/projects/{id}/builds` → `409 INVALID_STATE`. This work item is fully
blocked until a product owner provides real OpenRouter configuration; QA
will not fabricate AI output to work around this.

**Priority:** P0 (blocked, not skipped — this is the top re-prioritization
candidate once the dependency clears).

**Estimated effort:** 4h execution + 0.5h setup, once unblocked.

**Acceptance / completion criteria:** Every `AI-*` case executed with a
recorded PASS/FAIL against real AI output; any case where AI-authored
content or a compiler defect altered executable HTTP behavior is filed as a
**Critical** bug immediately (this is the one category where a single
confirmed failure should stop and escalate, per the product's own
non-negotiable rule).

**Deliverables:** Executed `AI-*` rows; any bugs found here get top billing
in `BUGS_FOUND.csv` and `QA_SUMMARY.md`.

**Status this round:** 0 executed, 18 BLOCKED (single named dependency: OpenRouter configuration).

---

## 7. Build Pipeline & Validation QA

**Description:** Verify the 9-state build state machine, cancellation,
coverage enforcement, operation exclusion, and the deterministic
build-time validator's hard-fail checks.

**Objective:** Prove the build pipeline is resumable, fails closed on
invalid/incomplete input, and never silently drops an operation.

**Scope:** `POST /projects/{id}/builds`, `/builds/{id}`, `/builds/{id}/events`, `/builds/{id}/validation`, `/builds/{id}/cancel`, `/projects/{id}/operation-exclusions`.

**Key test coverage:** `BUILD-001` through `BUILD-011`.

**Dependencies:** Work item 6's OpenRouter dependency for everything past
build creation; `BUILD-001` itself has **no** such dependency (it tests the
pre-flight rejection) and is already executed.

**Priority:** P0/P1.

**Estimated effort:** 2.5h execution + 0.25h setup, once unblocked.

**Acceptance / completion criteria:** State-machine transitions observed in
order at least once end to end; coverage/exclusion logic verified with
`fixtures/complex-api.yaml`'s two intentionally-excludable operations.

**Deliverables:** Executed `BUILD-*` rows.

**Status this round:** 1 PASS (`BUILD-001` — a genuinely valuable result: confirmed the platform fails fast and clearly, not silently), 8 BLOCKED, 2 deferred to regression (require controlled worker interruption / large synthetic spec).

---

## 8. Credentials & Deployment QA

**Description:** Verify credential CRUD/secrecy, deploy preflight
(READY-build requirement, scheme-mismatch rejection, staleness detection),
role-gated deployment, and per-project Docker network/secret isolation.

**Objective:** Prove a deployment can only happen from a valid, current,
scheme-consistent build, and that isolation between projects is real
(labeled networks, scoped secret bundles), not assumed.

**Scope:** `/projects/{id}/credentials*`, `/projects/{id}/deployments`,
`/deployments/{id}/*`, `/projects/{id}/rollback`, Docker network/label
inspection via platform-provided means only.

**Key test coverage:** `DEPLOY-001` through `DEPLOY-013`.

**Dependencies:** Work item 6 (a READY build is required for nearly every
case here); Docker access for network/label inspection.

**Priority:** P0/P1.

**Estimated effort:** 3h execution + 0.5h setup, once unblocked.

**Acceptance / completion criteria:** At least one full successful
deployment achieved and inspected; isolation claims (`DEPLOY-007`,
`DEPLOY-009`) verified with actual `docker network`/bundle inspection, not
just documentation trust.

**Deliverables:** Executed `DEPLOY-*` rows.

**Status this round:** 0 executed (all require a READY build), 8 BLOCKED, 5 not yet attempted independent of the OpenRouter dependency.

---

## 9. MCP Runtime & Tool Execution QA

**Description:** Verify the deployed runtime's health endpoints, inbound
auth enforcement, `tools/list`/`tools/call` correctness, and the runtime's
security hardening (undeclared-argument rejection, forbidden headers, URL
destination allowlisting).

**Objective:** Prove a real MCP client can list and call tools that reach
the real upstream API with exactly the request the source spec describes —
the literal end of the customer journey.

**Scope:** Per-project runtime `/healthz`, `/readyz`, `/mcp` (Streamable
HTTP), request-builder/URL-policy enforcement.

**Key test coverage:** `MCP-001` through `MCP-011`.

**Dependencies:** Work item 8 (a live deployment); a reachable mock/echo
upstream service matching `fixtures/simple-api.yaml` (needs to be prepared
before this work item can execute `MCP-003`).

**Priority:** P0/P1.

**Estimated effort:** 2.5h execution + 0.25h setup (mock upstream), once unblocked.

**Acceptance / completion criteria:** At least one real `tools/call`
executed end to end with the actual upstream request inspected and
confirmed to match the source spec exactly (`MCP-003` — the literal proof
of the product's core promise).

**Deliverables:** Executed `MCP-*` rows.

**Status this round:** 1 PASS (`MCP-011`, pre-build config availability — did not require a deployment), 9 BLOCKED, 1 deferred (needs a non-development install to test `disabled_dev` rejection).

---

## 10. Security & Isolation QA

**Description:** RBAC (cross-checked with work item 3), IDOR, credential
exposure, cross-project isolation, MCP-runtime input hardening (CRLF/path
traversal), and SSRF protection on source URL import.

**Objective:** Confirm the controls standing between "internal tool" and
"security incident" — since a deployed runtime executes real credentialed
HTTP calls against real upstream systems.

**Scope:** All endpoints, cross-cutting.

**Key test coverage:** `SEC-001` through `SEC-011`.

**Dependencies:** A second (`BUILDER`-role) test account (already created
this round); Work item 8 for the runtime-input-hardening cases
(`SEC-007`/`SEC-008`).

**Priority:** Security (treated as P0-equivalent for sign-off purposes).

**Estimated effort:** 2h execution + 0.25h setup.

**Acceptance / completion criteria:** All P0-equivalent security cases
executed; any FAIL is a Critical/Blocker bug requiring escalation before
this work item can close, regardless of what phase gate the overall QA
effort is in.

**Deliverables:** Executed `SEC-*` rows.

**Status this round:** 5 PASS (`SEC-001..004`, `SEC-010`), 4 BLOCKED (require a deployment), 2 not yet attempted.

---

## 11. UX & Error Recovery QA

**Description:** Verify wizard step-gating accuracy/messaging, error-message
safety (no leaked stack traces), request correlation IDs, and behavior
under interruption (browser refresh mid-build/deploy, partial-failure
recovery).

**Objective:** Confirm the platform communicates state and errors clearly
enough that an operator always knows what to do next, and that interrupting
a long-running operation never corrupts or loses progress.

**Scope:** Wizard/journey UI, SSE progress streams, error response shape.

**Key test coverage:** `UX-001` through `UX-008`.

**Dependencies:** Work items 4 (journey data), 7/8 (in-progress build/deploy for refresh tests).

**Priority:** P1/P2.

**Estimated effort:** 1.5h execution + 0.1h setup.

**Acceptance / completion criteria:** Error-shape consistency confirmed
across every negative test executed in this whole engagement (already
true); refresh-mid-operation cases executed once builds/deploys are
unblocked.

**Deliverables:** Executed `UX-*` rows.

**Status this round:** 4 PASS (`UX-001`, `UX-002`, `UX-007`, `UX-008`), 3 BLOCKED, 1 deferred (requires a browser-driven UI session).

---

## 12. Regression QA

**Description:** Once `OPENROUTER_API_KEY`/models are configured and/or any
filed bug is fixed, re-execute every currently `BLOCKED` or `FAIL` case.
Separately — and only on a fresh, disposable clone, never against this
persistent install — run the repository's own `tests/integration/full_stack_workflow.py`
acceptance harness as a deeper cross-check, per its own README's
disposable-only restriction.

**Objective:** Confirm the full pipeline works end to end at least once,
and that no fix introduced a new regression elsewhere.

**Scope:** All `BLOCKED`/`FAIL` rows in `GOOGLE_SHEETS_TEST_CASES.csv`; the disposable acceptance harness.

**Key test coverage:** `AI-*`, most of `BUILD-*`/`DEPLOY-*`/`MCP-*`, `BUG-001` re-verification.

**Dependencies:** OpenRouter configuration; a fresh disposable clone for the acceptance harness; any bug fixes to be re-verified.

**Priority:** P0 (this is the phase that actually proves the product works, not just that it fails safely).

**Estimated effort:** ~8h execution + 1h setup + 1h buffer (see `TESTING_PLAN.md` §5).

**Acceptance / completion criteria:** Zero P0 cases remain `BLOCKED`; every filed bug re-verified as fixed or formally accepted; disposable-harness run completed and its results cross-checked against this plan's manual findings.

**Deliverables:** Updated `GOOGLE_SHEETS_TEST_CASES.csv`, updated `BUGS_FOUND.csv`, a regression report appended to `QA_SUMMARY.md`.

**Status this round:** Not started (correctly gated behind work items 6/8/9's dependency).

---

## 13. QA Reporting & Summary

**Description:** Maintain `QA_SUMMARY.md` as the single, always-current,
non-technical-readable status of the whole engagement.

**Objective:** Give a reader with no codebase knowledge an accurate,
current picture: what's tested, what passed/failed/blocked, what's
verified-broken, and what to do next.

**Scope:** `QA_SUMMARY.md`.

**Dependencies:** All other work items (it aggregates them).

**Priority:** P1 (not customer-facing risk, but required for stakeholder visibility).

**Estimated effort:** 0.5h per update.

**Acceptance / completion criteria:** Counts in the summary always match the CSV exactly; planned vs. executed are never conflated; unexecuted tests are never counted as passed.

**Deliverables:** `QA_SUMMARY.md` (this round's version reflects the state as of 2026-09-02).

---

## Plane work-item summary table

| Work Item | Objective | Priority | Test Cases | Estimated Effort | Dependencies | Completion Criteria |
|---|---|---|---:|---:|---|---|
| 1. Repository & Workflow Analysis | Ground-truth the real workflow before planning | P0 | n/a | 3h | none | Done — findings folded into plan |
| 2. Test Planning & Test Case Design | Produce the plan, 103 test cases, 4 fixtures | P0 | n/a | 6h | Item 1 | Done — see deliverables |
| 3. Authentication & Access Control QA | Prove session/CSRF/RBAC enforced server-side | P0 | AUTH-001..010 | 1.75h | Running app | 9/10 executed, 1 bug filed |
| 4. Project Lifecycle QA | Prove project CRUD + journey gating accurate | P0/P1 | PROJECT-001..008 | 1.1h | Item 3 | 3/8 executed |
| 5. API Source Import & Parsing QA | Prove upload/versioning/deferred validation | P0/P1 | IMPORT-001..013 | 2.5h | Item 4, fixtures | 2/13 executed, rest blocked/pending |
| 6. AI Analysis & API→MCP Correctness QA | Prove AI can't alter HTTP behavior | P0 | AI-001..018 | 4.5h | **OpenRouter config (blocking)** | 0/18 — fully blocked |
| 7. Build Pipeline & Validation QA | Prove build state machine fails closed | P0/P1 | BUILD-001..011 | 2.75h | Item 6 (mostly) | 1/11 executed |
| 8. Credentials & Deployment QA | Prove deploy preflight + isolation | P0/P1 | DEPLOY-001..013 | 3.5h | Item 6 | 0/13 executed |
| 9. MCP Runtime & Tool Execution QA | Prove tools/call reaches upstream correctly | P0/P1 | MCP-001..011 | 2.75h | Item 8, mock upstream | 1/11 executed |
| 10. Security & Isolation QA | Prove RBAC/IDOR/isolation controls hold | Security | SEC-001..011 | 2.25h | Item 8 (partial) | 5/11 executed, 0 failures |
| 11. UX & Error Recovery QA | Prove clear errors + resilient long-ops UX | P1/P2 | UX-001..008 | 1.6h | Items 4, 7, 8 | 4/8 executed |
| 12. Regression QA | Full pipeline proof + fix re-verification | P0 | All blocked/failed rows | 10h | **OpenRouter config** | Not started |
| 13. QA Reporting & Summary | Keep stakeholder status current | P1 | n/a | 0.5h/update | All items | Current as of 2026-09-02 |
