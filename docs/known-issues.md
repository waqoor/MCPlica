# Known issues and concerns

This tracks real, currently-observed issues in MCPlica — things found while fixing bugs, running tests, or reading the code — not speculative or hypothetical risk. Each item states what was actually found, not a guess.

## Open bugs

- **MCP-005 (unresolved).** Operations mixing an unsupported auth scheme are now excluded from the compiled manifest instead of hanging the build wizard, but whether a build actually reaches `READY` with those operations correctly absent from the final manifest has never been verified. Every attempt has been blocked by OpenRouter's free-tier rate limit. Branch `mohd-ghnm-MCP-005-fix` exists locally, not pushed — not safe to merge as-is.
- **MCP-002 has no dedicated regression test.** The fix (rejecting operations that reference an undefined security scheme) shipped in v1.0.0-rc.2, is lint-clean, and was manually verified by code review, but a targeted test run matched zero tests. A future change to either parser could silently regress this in production without any test catching it.

## Data integrity concerns

MCP-011 (shipped in v1.0.0-rc.2) fixed `response_json`/`usage_json`/`cost_json` on `BuildAIRun` to store true SQL `NULL` going forward (`JSONB(none_as_null=True)`), but rows written **before** that fix may still hold a JSONB `null` literal instead of true SQL `NULL` in those columns. This means historical rows are inconsistent with current rows in a way that's invisible when read back as text (both render identically) — a query or report that specifically filters on `IS NULL` for these columns could silently miss old rows. A data backfill was explicitly called out as a separate follow-up when the fix was made, and has not been done.

## Product gaps

**Source names are not enforced as unique per project.** There is no database constraint and no application-level check preventing two sources with the same name and kind from coexisting on one project. Adding a source with a name that's already in use silently creates a second, independent source rather than a new version of the first — this can confuse the Sources tab (two similarly-named cards with no visible relationship) and the Tools tab (operations attributed to whichever source happened to be marked primary). Worth deciding whether to add a uniqueness constraint or an explicit rename/merge flow.

## Operational concerns

- **OpenRouter free-tier rate limits block build verification.** Multiple attempts to fully verify MCP-005 by driving a real build to `READY` have hit rate limits before completing — this is an external dependency limit, not a bug, but it's currently blocking one fix from being finished.
- **GitHub reports 1 high-severity Dependabot vulnerability** on the default branch. Not yet investigated — worth checking what it is.

## Known architectural limitations

Carried forward from the `1.0.0-rc.1` release notes and confirmed still current in the
[v1.0.0-rc.2 release notes](releases/v1.0.0-rc.2.md#boundaries):

- The supported production topology is a single Docker Compose host — no high availability, no orchestrator-specific deployment, no managed backup automation, no multi-host runtime scheduling.
- OpenRouter availability/model access, public DNS/TLS, host hardening, external OIDC providers, registry permissions, and backup/restore RPO/RTO all remain operator-owned production checks — MCPlica does not manage or verify these for you.
