# Operator user guide

MCPlica turns source evidence into a validated, manifest-driven MCP endpoint. The browser is a view/controller over typed API contracts; server authorization, validation, and deployment state remain authoritative.

## Roles

Admins manage users, installation/model settings, credentials, MCP access, deployment, and destructive project actions. Builders create and update projects/sources and review builds. An installation may explicitly allow builders to deploy, but the default is admin-only. Hidden or disabled controls are guidance, not the security boundary.

## Ten-step project workflow

1. **Project identity:** choose a durable name/slug and optional description. The slug becomes part of the MCP hostname; changing source content never creates a duplicate project.
2. **Primary API source:** upload an OpenAPI document or structured API inventory, or configure an allowlisted HTTPS URL. MCPlica creates a source record, then an immutable version.
3. **Documentation:** add optional Markdown, HTML, text, or PDF product/API evidence. Documentation enriches semantics but cannot define executable behavior that is absent from the API source.
4. **Server selection:** review the detected base URL and choose the intended upstream. Private/HTTP destinations require explicit operator policy and are rejected by default.
5. **Upstream authentication:** configure the API credential scheme or explicitly record that the upstream needs none. Secret values are write-only; rotate rather than reveal.
6. **Build:** start the canonical asynchronous build. One build ingests, parses, indexes, analyzes, compiles, validates, and packages; do not submit duplicate jobs when polling is slow.
7. **Progress and review:** inspect stage status and stable errors. Active builds update at bounded intervals and can be resumed from the durable project URL.
8. **Validation:** require exact operation accounting, 100% coverage after explicit exclusions, no blocking findings, a valid manifest, and runtime compatibility. Exclusions need a reason and remain auditable.
9. **MCP inbound access:** select static bearer or reviewed external OAuth/OIDC. A bearer token plaintext is displayed once. Copy it directly to the client secret manager; MCPlica stores only a verifier/prefix.
10. **Deploy:** choose a READY build, confirm inbound access, and deploy. The worker creates an isolated generic runtime, checks health, and records endpoint/image/manifest evidence. A failed replacement must not silently replace a healthy runtime.

The wizard URL retains project, build, and step identifiers so refresh/back navigation resumes durable server state. One-time plaintext secrets intentionally are not persisted in the browser and cannot be recovered after navigation.

## Ongoing work

The project workspace separates Overview, Sources, Tools, Documentation, Builds/Validation, Deployment/MCP access, Credentials, and Settings. Global Builds, Deployments, Activity, and installation Settings pages provide cross-project operations with bounded queries.

- Uploading identical source bytes may deduplicate a version; it does not erase history.
- Changing sources/settings creates a new build and diff. Deployed build artifacts remain immutable.
- Stop/restart operate on the recorded deployment. Rollback selects a prior deployment and creates a new deployment record from that target; it does not mutate history.
- Credential rotation and MCP token rotation/revocation are server-side audited actions. Existing values are never redisplayed.
- Activity filters should use actor, project, event type, and time window; request IDs correlate UI errors with sanitized server logs.

## Failure recovery

Use the displayed stable error code and request ID. Fix the earliest failing source/configuration or dependency and retry through the canonical action. Never weaken a failed validation, auth, network, or health gate. For system-wide issues, follow `operations/runbook.md`.

## Accessibility and browser support

The UI provides keyboard-visible focus, skip navigation, semantic labels/status, responsive tables/workspaces, reduced-motion support, and non-color-only status text. Release journeys run in Chromium, Firefox, WebKit, and a compact mobile viewport. Report functional accessibility defects as bugs with browser, input method, and reproduction details.
