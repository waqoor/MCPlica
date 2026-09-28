# Bug reports

This report covers 10 bugs found and fixed in MCPlica (the OpenAPI/API-Inventory-to-MCP-server build pipeline) during this engagement. Each section states what was broken, the root cause, the fix, and how it was verified. All 9 fixes below were merged into `master` via PR #83 and shipped in **v1.0.0-rc.2** (see [the release notes](releases/v1.0.0-rc.2.md)), except MCP-005, which remains unresolved on its own unmerged branch — its code change exists but end-to-end verification is blocked by an external OpenRouter rate limit, not by a defect in the fix itself.

## MCP-001 — Canonicalization concurrency bug

Concurrent identical build-canonicalization requests coalesce onto one shared in-flight `asyncio.Future`, so only one caller (the "leader") actually does the work while the rest ("followers") await the same future. If the leader's own request was cancelled, cancelling that shared future also raised `CancelledError` in every follower — even though the followers' own callers never cancelled them.

**Root cause:** `canonicalize()` had no way to distinguish "my own task was cancelled" from "the future I was waiting on was cancelled by someone else."

**Fix:** a follower that receives `CancelledError` from the shared future now checks `asyncio.current_task().cancelling()`. If that count is 0, the cancellation wasn't its own — it retries the call as the new leader instead of propagating the error. Also fixed 2 `ruff` line-length violations by introducing a `_CacheKey` type alias.

**Verified:** added a regression test that cancels the leader mid-flight and asserts the follower still completes instead of raising. Lint clean, 3/3 tests pass, confirmed on a clean run against the actual fixed code (an earlier run had accidentally verified the test against the wrong branch and was redone properly).

Branch: `mohd-ghnm-MCP-001-fix` — pushed, merged into `master`, released in v1.0.0-rc.2.

## MCP-002 — Undefined security scheme references

An OpenAPI or API Inventory document could reference a security scheme name in an operation's `security` requirement that was never defined in the document's `securitySchemes`. Both parsers silently admitted this instead of rejecting the document.

**Fix:** both `parse_openapi()` and `parse_api_inventory()` now collect every scheme name referenced across all operations and raise `SourceParseError` listing the undefined names if any aren't present in `securitySchemes`.

**Verified:** lint clean. No dedicated regression test exists yet for this specific case — a filtered test run matched zero tests (390 deselected), meaning this fix currently has manual code review as its only verification, not an automated test. Worth adding a test before this is considered fully covered.

Branch: `mohd-ghnm-MCP-002-fix` — pushed, merged into `master`, released in v1.0.0-rc.2.

## MCP-003 — Execution ownership loss masked

When a build's execution lease expired mid-attempt, `require_build_execution_owner()` raised a generic `InvalidStateError`. The failure-recording path then re-checked ownership as part of writing the failure audit entry — but that recheck failed identically (the lease really was gone), and since the error type was indistinguishable from any other `InvalidStateError`, this doomed recheck raised through the handler and masked the real, original failure behind an opaque error instead of recording it.

**Fix:** execution-lease staleness now raises a dedicated `ExecutionOwnershipError` instead of the generic `InvalidStateError`. The failure-recording path catches this specifically: if the *original* failure being recorded is itself an `ExecutionOwnershipError`, it skips the audit write (re-checking would fail identically) instead of letting that doomed recheck raise and mask the failure. Also added Postgres constraint/detail diagnostic logging on `IntegrityError`, and cached the resolved OpenRouter API key for a build job's lifetime instead of re-fetching and decrypting it on every request.

**Verified:** lint clean, 6/6 tests pass.

Branch: `mohd-ghnm-MCP-003-fix` — pushed, merged into `master`, released in v1.0.0-rc.2.

## MCP-004 — Path-level OpenAPI servers

The "no server URL" check ran immediately after resolving only root-level `servers`, before the per-path loop that registers path-level servers ever executed. A spec declaring servers only under a path item (valid per OpenAPI 3.1, and used by real-world specs like Open-Meteo's) was rejected outright at the wizard's server-selection step, even though the parser already had code to handle path-level servers — it just never reached it. This also silently broke the manual "Resolution base URL" override, since the early raise fired before that fallback could matter.

**Fix:** moved the check to after the full path/operation loop, so it inspects the accumulated servers registry (root + path + operation level) instead of only the root-level list collected before any path was processed.

**Verified:** live-tested with a spec declaring servers only at the path level (Open-Meteo's two API hosts) — both now surface correctly as selectable options at the server-selection step, and the wizard proceeds normally afterward. Lint clean, 27/27 tests pass.

Branch: `mohd-ghnm-MCP-004-fix` — pushed, merged into `master`, released in v1.0.0-rc.2.

## MCP-005 — Unsupported auth schemes (unresolved)

**Status: unresolved / unverified — not merged.**

Operations that mix an unsupported authentication scheme (e.g. `api_key` mixed with OAuth2 implicit in the same document, per the original bug report against Swagger Petstore v3) caused the build wizard to hang at Step 5 instead of excluding those operations and continuing.

**Fix (written, not yet fully verified):** operations referencing unsupported auth schemes are now excluded from the compiled manifest instead of blocking the whole build, with a warning listing which operations were excluded.

**Verified so far:** re-tested against the real bug report source — Step 5 now completes instead of hanging, and the warning correctly lists the excluded operations.

**Not yet verified:** that a build actually reaches `READY` status with those operations absent from the final compiled manifest. Every attempt at that specific check has been blocked by OpenRouter's free-tier rate limit, not by a problem in this fix. This branch has not been pushed and needs that final check before it's safe to merge.

Branch: `mohd-ghnm-MCP-005-fix` — not pushed.

## MCP-006 — Source list pagination

The Sources tab's `list_source_summaries()` query paginated raw, ungrouped source rows with `LIMIT`/`OFFSET`. When "show previous sources" was on, a source's older versions (same name + kind) could land on a different page than its current version. The frontend groups sources by name+kind per page, so an orphaned older version with no group-mate on that page rendered as if it were the current/latest source — a stale version silently presented as current.

**Fix:** the query now pages over distinct (non-superseded) sources only, then pulls every sibling version of each selected source regardless of row count, so a version group can never be split across a page. This also corrected `total` to always count distinct sources rather than raw version rows.

**Verified:** added an integration test seeding a two-version group followed by a second source, requesting page size 1 — confirms both versions of the first group return together instead of splitting. Ran against the real Postgres dev database (not a mock): lint clean, both the new test and the existing pagination test pass.

Branch: `mohd-ghnm-MCP-006-fix` — pushed, merged into `master`, released in v1.0.0-rc.2.

## MCP-007 — Wizard error alert spacing

The `MutationError` alert boxes in the project setup wizard had no top margin, so they visually merged with whatever content sat directly above them — most visibly the three info cards on the "Start build" step.

**Fix:** wrapped all 7 occurrences across the wizard's step components in the same `mt-5` spacing already used elsewhere in the file for `Alert` elements.

**Verified:** typecheck clean, no other changes in the diff.

Branch: `mohd-ghnm-MCP-007-fix` — pushed, merged into `master`, released in v1.0.0-rc.2.

## MCP-011 — Build AI run NULL storage

Builds intermittently crashed with an `IntegrityError` on `ck_build_ai_runs_outcome` whenever an AI operation genuinely failed — not a race condition, despite failing at inconsistent operation counts across runs. SQLAlchemy's `JSONB` type stores a Python `None` as the JSON value `null` by default, not true SQL `NULL`, unless the column declares `none_as_null=True`. The check constraint's "failed" branch requires `response_json IS NULL` (true SQL `NULL`); a stored JSONB `null` fails that check even though the row looks identical to a valid `NULL` when read back as text — which is why this was misdiagnosed as a race condition for so long.

**Fix:** `response_json`, `usage_json`, and `cost_json` on `BuildAIRun` now declare `JSONB(none_as_null=True)`. Also expanded diagnostic logging to surface the full exception chain, root-cause message, and Postgres constraint detail instead of only the outermost exception type — this diagnostic logging is what let the root cause be pinned down instead of guessed at.

**Verified:** live-tested — a build with a genuinely failing AI operation now completes the write cleanly and surfaces the real, specific failure reason instead of crashing with an opaque database error. Lint clean, 1/1 test passes on the pushed state.

**Note:** rows written before this fix may still have JSONB `null` stored in these columns instead of true SQL `NULL`; a data backfill is a separate follow-up, not required for this fix.

Branch: `mohd-ghnm-MCP-011-fix` — pushed, merged into `master`, released in v1.0.0-rc.2.

## MCP-012 — Source deletion confirmation dialog

Deleting a source on the Sources tab triggered a native browser `window.confirm()` popup instead of an in-app dialog, inconsistent with the rest of the site (project deletion already used an in-app dialog). Same category of issue as a native-confirm bug fixed earlier elsewhere; this one was missed on the Sources page specifically.

**Fix:** delete now opens an in-app `Dialog` with Cancel/Delete actions, matching the existing pattern used for project deletion.

**Verified:** typecheck clean, no stray comments in the diff.

Branch: `mohd-ghnm-MCP-012-fix` — pushed, merged into `master`, released in v1.0.0-rc.2.

## MCP-013 — Persisted embedding model

`IndexingService`'s completion call passed `model=actual_model` — the model name the AI provider happened to echo back in its response — instead of `model=embedding_model`, the model that was actually configured and requested for the build. A completed document index generation's persisted `embedding_model` field could therefore drift from what was actually requested.

**Fix:** changed the argument to `model=embedding_model` in `backend/app/services/indexing/service.py`.

**Verified:** lint clean, 3/3 tests pass, including a dedicated regression test (`test_index_persists_the_configured_embedding_model_not_the_provider_alias`) added for this fix.

Branch: `mohd-ghnm-MCP-013-fix` — pushed, merged into `master`, released in v1.0.0-rc.2.
