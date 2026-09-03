# QA fixtures

Four small, purpose-built OpenAPI documents. Each is designed around specific
test cases in `../GOOGLE_SHEETS_TEST_CASES.csv` rather than being a generic
sample — see the "Which test IDs use it" row below for the exact mapping.

## simple-api.yaml

**Contains:** A minimal, fully valid OpenAPI 3.0.3 "Bookstore" API. One
resource (`books`), three operations (`listBooks`, `createBook`, `getBook`),
one bearer security scheme, one query enum, one required nested object
response.

**Tests:** The golden-path customer journey end to end — import, parse, AI
analysis, compile, build, deploy, tool call — with the least schema
complexity possible, so a failure anywhere in the pipeline can be attributed
to that pipeline stage rather than to spec complexity.

**Test IDs:** `IMPORT-001`, `AI-001`, `AI-002`, `AI-003`, `AI-004`,
`AI-016`, `AI-017`, `BUILD-002`, `BUILD-005`, `MCP-001` through `MCP-004`.

**Why useful:** Every schema-complexity fixture below builds on the
assumption that the *simple* path already works. This is also the fixture
used in `IMPORT-001`, which is already executed and passing against the
live install.

## complex-api.yaml

**Contains:** OpenAPI 3.1.0 "Order Management" API. Two servers (explicit
multi-server mapping), API-key-in-header auth, nested request/response
objects, an array of nested objects, an enum, path/query/header params, and
**two deliberately non-compliant operations**: `exportOrders` (a cookie
parameter — unsupported by the MCP runtime) and `generateShippingLabel` (a
request body whose only media type is `application/pdf` — outside the
supported json/form/multipart set). Both parse successfully (the defect is
compiler-level, not parser-level) so this fixture is usable today for
`IMPORT-*` even though the compiler-level assertions are currently blocked.

**Tests:** Schema fidelity under real complexity (nested objects, arrays,
enums, multi-server, header/query serialization styles) and the compiler's
two deterministic hard-rejection paths for unsupported parameter locations
and media types.

**Test IDs:** `AI-005` through `AI-011`, `AI-018`, `BUILD-006`,
`DEPLOY-003`.

**Why useful:** These two non-compliant operations are the concrete basis
for `BUILD-006` (operation exclusion with a reason) — a customer should be
able to exclude `exportOrders`/`generateShippingLabel` and still get a
`READY` build for the other five operations, rather than the whole build
failing.

## invalid-api.yaml

**Contains:** Otherwise-valid OpenAPI 3.1 with exactly one defect: the
operationId `getWidget` is reused on two different paths
(`/widgets/{widgetId}` and `/widgets/{widgetId}/details`). Confirmed hard-fail
in `backend/app/parsers/openapi/parser.py:1072`.

**Tests:** That an invalid spec is accepted at **upload** time (confirmed
live: `201 Created`, deferred validation) and only rejected later, during a
build's `PARSING` stage, with a specific, locatable finding.

**Test IDs:** `IMPORT-002` (executed, passing), `IMPORT-007`.

**Other invalid-input classes**, to keep the fixture count at four, are
covered as minimal tester-authored edits of this same file rather than as
separate files — see "Negative source-fixture catalog" in
`../TESTING_PLAN.md` for the exact one-line edit and expected result for
each (`IMPORT-008` through `IMPORT-011`): missing `info.title`, an
unresolved `$ref`, a relative server URL with no project default base URL,
and a non-OpenAPI (Swagger 2.0) document.

## semantic-confusion-api.yaml

**Contains:** Six valid, deterministic operations deliberately arranged in
three confusable pairs with overlapping vocabulary in their
summaries/descriptions: `cancelPayment` vs `refundPayment` (both mention
"reverse"/"void"/"cancel"/"refund"), `getUser` vs `getUserProfile`
(near-identical naming/shape, different resources), `deleteOrder` vs
`cancelOrder` (semantic near-synonyms, different HTTP methods/paths).

**Tests:** Whether AI-generated semantic enrichment (title/description/
category — the *only* fields AI is allowed to write) gets correctly
attributed to its own operation via `operation_key`, and — more importantly
— that even a "confused" AI response cannot alter the underlying HTTP
method/path/params, since those are set once during deterministic
canonicalization and never touched by `AnalysisService.apply()`
(`backend/app/services/analysis/service.py`).

**Test IDs:** `AI-012`, `AI-013` (the two highest-value cases in this
engagement — see `TESTING_PLAN.md` §1).

**Why useful:** No equivalent fixture exists anywhere else in the
repository. `docs/security/threat-model.md`'s "AI prompt injection invents
tools" risk row calls for exactly this kind of adversarial-naming fixture
but doesn't provide one — this fills that documented gap.

## A note on execution status

Every fixture above is already usable today for the **upload/parse**-level
test cases (`IMPORT-001`, `IMPORT-002`). The **AI/compile/build/deploy/MCP**
test cases that reference these fixtures are all currently `BLOCKED` in
`GOOGLE_SHEETS_TEST_CASES.csv` because `OPENROUTER_API_KEY` and the
analysis/validation/embedding models are not configured on this install —
confirmed live via `POST /projects/{id}/builds` → `409 INVALID_STATE:
"Build models are not configured: analysis_model, validation_model,
embedding_model"`. See `TESTING_PLAN.md` §8 Risk 1 and `QA_SUMMARY.md`.
