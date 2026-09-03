# MCPlica Customer Workflow — QA Summary

**Prepared for:** Anyone who needs the current QA status without reading the codebase
**Date:** 2026-09-02
**Environment:** Local Docker Compose install (`http://localhost:8081` UI / `http://localhost:8000` API), all 11 core services healthy

---

## What is MCPlica, and what was tested

MCPlica takes a company's OpenAPI specification, uses AI to enrich it with
readable descriptions, and turns it into an MCP server — a small program
that AI assistants (or any MCP client) can use to call that company's API.
The entire product promise rests on one guarantee: **the generated tool
calls the same HTTP method, path, and parameters as the original API —
AI is only allowed to make it easier to understand, never to change what it
actually does.**

This round of QA covered the full customer journey — log in, create a
project, import an API spec, have AI analyze it, generate MCP tools,
validate/build, configure credentials and access, deploy, and call a tool —
plus the security, negative, and recovery paths around it.

## Scope

- **In scope:** Everything an operator needs to go from "fresh install" to
  "a working, callable MCP tool," plus the security and negative testing
  necessary to trust that journey.
- **Out of scope:** Production TLS/DNS hardening, CI/release automation,
  and the repository's own disposable end-to-end test harness (which
  cannot safely run against this persistent install — see Blockers below).

## Planned test coverage

| Metric | Count |
|---|---:|
| **Total planned test cases** | **103** |
| P0 (core workflow) | 40 |
| P1 (negative/edge/recovery) | 38 |
| P2 (lower-priority edge/UX) | 12 |
| Security (dedicated) | 13 |

**Estimated total QA effort:** ~27.5 hours (~20.5h execution + ~3.7h setup + ~3.4h buffer), of which **~19 hours (the AI-correctness, build-pipeline, deployment, and MCP-runtime phases) cannot proceed until a real `OPENROUTER_API_KEY` and AI models are configured.** Full basis for this estimate is in `TESTING_PLAN.md` §5.

## Executed this round

| Result | Count | % of planned |
|---|---:|---:|
| **PASS** | 23 | 22% |
| **FAIL** | 1 | 1% |
| **BLOCKED** | 59 | 57% |
| **Not yet attempted** | 20 | 20% |

**Nothing here is counted as passed unless it was actually executed with a
real, observed result.** The 20 "not yet attempted" cases are P1/P2/Security
items this round's time did not reach — they are not failures, they are
simply next in line.

### P0 (core-workflow) breakdown specifically

| Result | Count |
|---|---:|
| PASS | 11 |
| FAIL | 1 |
| BLOCKED | 25 |
| Not yet attempted | 3 |

25 of 40 P0 cases are blocked by a single, clearly identified dependency
(see below) — not by 25 separate problems.

## Verified bugs found: 1 (fixed in integration; live re-verification pending)

| Bug ID | Title | Severity | Priority | Status |
|---|---|---|---|---|
| `BUG-001` | `GET /api/v1/auth/me` returns `null` for `created_at`/`updated_at`/`last_login_at`, while `GET /api/v1/users` correctly returns real values for the identical account at the same instant | Low | P2 | Fixed in integration; automated regression passed; live endpoint re-verification pending |

Root cause located precisely: `backend/app/api/auth.py:128-137` constructs
the response object manually and omits those three fields, which then
silently default to `null` rather than erroring. Full reproduction and code
citation in `BUGS_FOUND.csv` and `qa/customer-workflow/evidence/BUG-001-auth-me-null-timestamps.md`.
The integration fix retains the three timestamps in the safe authenticated
identity and validates the `/me` response from that identity. The original
live result remains a FAIL until the Docker endpoint is explicitly re-run.

**No other verified bugs were found.** Every other executed test — including
CSRF enforcement, session revocation on logout, all three RBAC checks
(builder blocked from credentials/deletion/user-management), the IDOR/404
check, cookie security attributes, and the pre-flight build rejection — behaved
exactly as documented. That is a genuinely good result, not a gap in
testing: it means the parts of the platform this round could reach are
working correctly.

## Current blocker (the one thing gating ~19 hours of remaining P0 work)

**`OPENROUTER_API_KEY` (and the analysis/validation/embedding model
choices) are not configured on this install.** Confirmed live and
reproducibly:

```
POST /api/v1/projects/{id}/builds
→ 409 INVALID_STATE
   "Build models are not configured: analysis_model, validation_model, embedding_model"
```

This is not a bug — it matches the documented design ("a build cannot enter
AI stages if required models are not configured," `design_document.md`
§13.1) — but it means **no build can even be created**, which blocks
everything downstream of it: AI analysis, MCP manifest generation, build
validation, deployment, and MCP runtime/tool-call testing (Phases 4-7 in
`TESTING_PLAN.md`, work items 6-9 in `PLANE_WORK_ITEMS.md`).

**What's needed to unblock:** A real OpenRouter API key and model choices
from the product owner, set either in `.env` (`OPENROUTER_API_KEY`,
`OPENROUTER_ANALYSIS_MODEL`, `OPENROUTER_VALIDATION_MODEL`,
`OPENROUTER_EMBEDDING_MODEL`) or via the in-app Settings after login
(`PUT /api/v1/settings/openrouter`, `PUT /api/v1/settings/models`). QA did
not fabricate a key or mock AI output to work around this, per this
engagement's hard rules.

## Highest-risk area (once unblocked)

**API → MCP correctness (`AI-*`, 18 test cases, all currently blocked).**
This is the single highest-value area in the entire plan (see
`TESTING_PLAN.md` §1) because a silent fidelity defect here — AI subtly
changing a method, path, or required parameter — is invisible until it
causes a real incident against a customer's live upstream API. Two fixtures
were purpose-built for this: `complex-api.yaml` (schema complexity) and
`semantic-confusion-api.yaml` (adversarially similar operation
names/descriptions, designed to catch AI attribution errors). Neither could
be exercised this round for the reason above. **This should be the first
thing re-run once OpenRouter is configured**, ahead of general regression.

## Documentation/implementation discrepancies found

None that affect testability in a material way. Two minor notes recorded
(not bugs):
1. There is no standalone MCP manifest JSON-Schema document — the
   authoritative schema lives in code (`packages/contracts/`), not in
   `docs/`. Noted as a documentation gap for future testers, not a defect.
2. Two distinct error codes exist for what is conceptually the same
   "manifest too large" constraint, checked at two different pipeline
   gates (`MANIFEST_RUNTIME_SIZE_LIMIT_EXCEEDED` at build validation vs.
   `MANIFEST_EXCEEDS_RUNTIME_LIMIT` at deploy preflight) — likely
   intentional (two real gates), captured as `BUILD-010` to verify which
   fires when.

Full detail in `TESTING_PLAN.md` (negative-fixture catalog and glossary
note sections).

## Recommended next testing phase

1. **Obtain OpenRouter configuration** from the product owner — this is the
   single action that unblocks the largest share of remaining work (see
   `PLANE_WORK_ITEMS.md` work item 6).
2. Re-run the 18 `AI-*` cases first, using the two fixtures built for
   exactly this purpose.
3. Continue through Build → Credentials/Deployment → MCP Runtime
   (`BUILD-*`, `DEPLOY-*`, `MCP-*`), which unblock in sequence as each
   pipeline stage becomes reachable.
4. Finish the 20 not-yet-attempted P1/P2/Security cases in parallel — they
   have no OpenRouter dependency and can run independently at any time
   (e.g. `AUTH-009` refresh rotation, `PROJECT-004/005` negative cases,
   `IMPORT-003/004` versioning, `SEC-009/011`).
5. Run the full regression pass (`PLANE_WORK_ITEMS.md` work item 12) once
   the above lands, including a **separate, disposable-clone** run of the
   repository's own `tests/integration/full_stack_workflow.py` acceptance
   harness as a deeper cross-check — never against this persistent
   install.

## Plane work-item summary

Full detail, including per-item description/objective/scope/acceptance
criteria, is in `PLANE_WORK_ITEMS.md` (no Plane integration was available
in this environment, so these are prepared for manual import rather than
created directly).

| Work Item | Priority | Test Cases | Est. Effort | Status this round |
|---|---|---:|---:|---|
| 1. Repository & Workflow Analysis | P0 | n/a | 3h | Done |
| 2. Test Planning & Test Case Design | P0 | n/a | 6h | Done |
| 3. Authentication & Access Control QA | P0 | AUTH-001..010 | 1.75h | 8 PASS / 1 FAIL / 1 BLOCKED |
| 4. Project Lifecycle QA | P0/P1 | PROJECT-001..008 | 1.1h | 3 PASS / 5 pending |
| 5. API Source Import & Parsing QA | P0/P1 | IMPORT-001..013 | 2.5h | 2 PASS / 5 BLOCKED / 6 pending |
| 6. AI Analysis & API→MCP Correctness QA | P0 | AI-001..018 | 4.5h | **0 executed — fully blocked** |
| 7. Build Pipeline & Validation QA | P0/P1 | BUILD-001..011 | 2.75h | 1 PASS / 8 BLOCKED / 2 deferred |
| 8. Credentials & Deployment QA | P0/P1 | DEPLOY-001..013 | 3.5h | 0 executed / 8 BLOCKED / 5 pending |
| 9. MCP Runtime & Tool Execution QA | P0/P1 | MCP-001..011 | 2.75h | 1 PASS / 9 BLOCKED / 1 deferred |
| 10. Security & Isolation QA | Security | SEC-001..011 | 2.25h | 5 PASS / 4 BLOCKED / 2 pending |
| 11. UX & Error Recovery QA | P1/P2 | UX-001..008 | 1.6h | 4 PASS / 3 BLOCKED / 1 pending |
| 12. Regression QA | P0 | All blocked/failed rows | 10h | Not started (correctly gated) |
| 13. QA Reporting & Summary | P1 | n/a | 0.5h/update | Current as of this document |

---

*Full test-by-test detail: `GOOGLE_SHEETS_TEST_CASES.csv`. Bug detail:
`BUGS_FOUND.csv`. Test strategy and rationale: `TESTING_PLAN.md`. Fixture
design: `fixtures/README.md`.*
