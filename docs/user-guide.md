# Operator user guide

MCPlica turns source evidence into a validated, manifest-driven MCP endpoint. The browser is a view/controller over typed API contracts; server authorization, validation, and deployment state remain authoritative.

## Roles

Admins manage users, installation/provider/model settings, credentials, MCP access, deployment, and destructive project actions. Builders create and update projects/sources and review builds. An installation may explicitly allow builders to deploy, but the default is admin-only. Hidden or disabled controls are guidance, not the security boundary.

## Ten-step project workflow

1. **Project identity:** choose a durable name/slug and optional description. The slug becomes part of the MCP hostname; changing source content never creates a duplicate project.
2. **Primary API source:** upload an OpenAPI document or structured API inventory, or configure an allowlisted HTTPS URL. MCPlica atomically creates the source and first immutable version. Exactly one executable source is primary; changing or deleting it requires an explicit replacement so a failed partial action cannot strand the project.
3. **Documentation:** add optional JSON, Markdown, TXT, CSV, XLSX, DOCX, HTML, or text-extractable PDF product/API evidence, up to 100 MB per upload by default. Documentation is indexed and supplied as bounded evidence to build-time AI when documentation analysis is enabled, but it cannot define executable behavior that is absent from the API source.
4. **Server selection:** review the detected base URL and choose the intended upstream. The project selection resolves ambiguous inherited/root candidates; explicit OpenAPI path- and operation-scoped servers remain attached to those operations. Private/HTTP destinations require explicit operator policy and are rejected by default.
5. **Upstream authentication:** bind each discovered required security scheme to a compatible project credential, or preserve a source-declared anonymous alternative. Secret values are write-only; rotate rather than reveal. Rotation replaces only the secret material and preserves its scheme/name/location binding, even if the source has since drifted. To remap authentication, create a replacement credential and a new Build. Bearer, Basic, header/query API key, and OAuth client-credentials mappings are validated server-side.
6. **Build:** start the canonical asynchronous build. One build ingests, parses, indexes, analyzes, compiles, validates, and packages; do not submit duplicate jobs when polling is slow.
7. **Progress and review:** inspect status, the exact persisted pipeline stage, queue/admission state, and stable errors. Cancellation first shows **requested** and becomes terminal only after the worker acknowledges a checkpoint. Active builds update at bounded intervals and can be resumed from the durable project URL.
8. **Validation:** require exact operation accounting, 100% coverage after explicit exclusions, no blocking findings, a valid manifest, and runtime compatibility. The pinned production runtime must initialize, list the candidate tools/resources, and complete a schema-valid successful probe for every enabled tool; an MCP error result cannot satisfy this gate. Exclusions need a reason and remain auditable. The Operations page shows the immutable exclusion state captured by the selected build separately from the project's current policy. Adding or removing a policy never changes an existing build; request a rebuild to capture the new policy, validate it, and then deploy it explicitly.
9. **MCP inbound access:** select static bearer or reviewed external OAuth/OIDC after the Build is READY. A bearer token plaintext is displayed once. Copy it directly to the client secret manager; MCPlica stores only a verifier/prefix. Auth changes are applied as a hashed runtime overlay and show pending/failed/effective state without rebuilding.
10. **Deploy:** choose a READY build in the URL-backed selector, confirm inbound access, and deploy. Synchronous preflight rejects stale inputs, missing artifacts/secrets, invalid auth, incompatible runtime, or an oversized manifest before returning `202`. The worker then creates an isolated generic runtime, checks exact container/edge identity and health, and records activation evidence. A failed replacement must not silently replace a healthy runtime.

The wizard URL retains project, build, and step identifiers, while `/projects/{id}/journey`
reconstructs completion from authoritative source, routing, credential, Build, access, and active
deployment records. Refresh/back navigation therefore resumes server truth instead of local
checkboxes. One-time plaintext secrets intentionally are not persisted in the browser and cannot
be recovered after navigation.

## Ongoing work

The project workspace separates Overview, Sources, Tools, Documentation, Builds/Validation, Deployment/MCP access, Credentials, and Settings. Global Builds, Deployments, Activity, and installation Settings pages provide cross-project operations with bounded queries. Tools uses a URL-backed immutable build selector: it defaults to the actively served build when available, otherwise the latest build with a canonical snapshot. A newer queued or failed build is shown as current progress but does not hide older evidence. Build detail exposes the schema-validated manifest, raw manifest download, executable-configuration fingerprint, model/provider/prompt/context hashes, retrieved chunk IDs, usage/cost metadata, response hashes, and full validation counts/source references/details; chain-of-thought is neither stored nor returned. Changing a bound source version, base URL, selected server, or operation routing makes older builds stale for new activation while leaving historical artifacts and an already-running deployment unchanged; rebuild and validate before deploying again.

The admin-only **Settings > Providers** page manages the OpenRouter credential independently from
model policy. It never reads a stored key back into the browser: entering a value creates or
rotates the encrypted PostgreSQL override, while an environment key remains the fallback when no
override exists. **Test connection** performs a live authenticated model-catalog request. Its
status rail separates configured credential, provider reachability, and build readiness; build
readiness also requires analysis, validation, and embedding selections under **Settings > Models**.
The API base shown there is `https://openrouter.ai/api/v1`.

Deployment history offers **Rollback** only for a former runtime whose exact build/container/image/
manifest identity has durable successful-activation evidence. The active runtime and candidates that
failed or stopped before activation are never rollback targets. Rollback creates a new deployment;
it does not mutate the historical row or build.

- Uploading identical source bytes may deduplicate a version; it does not erase history. If those
  bytes belong to an older version, that immutable version becomes the explicitly selected current
  version again. The source card, the next Build, refresh validators, and retention protection all
  follow this accepted selection rather than whichever version was created most recently.
- Source cards expose bounded immutable version history and parser/index evidence without an N+1 request fan-out.
- Changing sources/settings creates a new build and diff. Deployed build artifacts remain immutable.
- Administrators can configure Build-count and source-version-age retention in Settings. The newest/active/deployed evidence remains protected; only source versions strictly older than the configured day cutoff are eligible. Project/source deletion returns an asynchronous cleanup record, and administrators can inspect durable progress or retry errors through the cleanup-jobs API/activity audit.
- Source findings identify the exact immutable version and parser stage. When available, the
  Sources page shows a JSON/YAML pointer and one-based line/column plus sanitized structured
  evidence. A failure in a secondary source is not displayed against the valid primary source.
- Documentation may be indexed successfully while its fully embedded runtime resource manifest is
  too large. In that case validation reports `MANIFEST_RUNTIME_SIZE_LIMIT_EXCEEDED` with the exact
  byte count and the Build remains failed; reduce published documentation content or have an
  administrator review the installation-wide runtime manifest limit before rebuilding.
- Stop/restart operate on the recorded deployment. Rollback selects a prior deployment and creates a new deployment record from that target; it does not mutate history.
- Credential rotation and MCP token rotation/revocation are server-side audited actions. Existing values are never redisplayed. Upstream credential binding fields are read-only during rotation; a mapping change requires a replacement credential and new Build. Authentication-only maintenance always targets the exact active Build even when a newer source is pending; it never activates that source implicitly. Revoking the final valid verifier commits the revocation and schedules runtime shutdown instead of preserving access or creating an unauthenticated replacement. Treat the change as pending until shutdown is observed, and follow the runbook if the worker reports a retryable or failed effect.
- Project/build/deployment/search filters and meaningful pagination live in URL parameters, so links and browser back/forward restore the same view. Dirty settings and wizard forms warn before navigation; dialog forms submit with Enter.
- Activity filters use actor, project, event type, and validated inclusive date ranges. Stable error codes and request IDs remain visible with retry/remediation guidance so operators can correlate sanitized logs.
- Installation settings expose provider credentials, model policy, deploy policy, hostname, bounded upload/operation/chunk/build limits, and retention as separate route-backed sections. User management supports display-name/password updates, safe disable/demotion confirmation, last-admin protection, and session revocation.

## Failure recovery

Use the displayed stable error code and request ID. Fix the earliest failing source/configuration or dependency and retry through the canonical action. Never weaken a failed validation, auth, network, or health gate. For system-wide issues, follow `operations/runbook.md`.

The browser refreshes an expired access cookie once through the rotating refresh-cookie contract,
replays safe requests, and preserves the intended protected destination. Logout calls the server
revocation endpoint; if revocation is not confirmed, the UI reports that the server session may
remain active rather than presenting a false signed-out state.

## Accessibility and browser support

The UI provides keyboard-visible focus, skip navigation, semantic forms/labels/status, focus-trapped and restoring modals, responsive tables/workspaces, reduced-motion support, localized numeric units, and non-color-only status text. Only the active responsive shell logo is rendered; the founder-supplied transparent PNG assets are format- and alpha-checked under a 600 KB aggregate budget. Release journeys run in Chromium, Firefox, WebKit, and a compact mobile viewport. Report functional accessibility defects as bugs with browser, input method, and reproduction details.
