# User guide overview

> A page-by-page walkthrough for readers who haven't used MCPlica before. [`user-guide.md`](user-guide.md)
> remains the authoritative operator reference (roles, recovery semantics, accessibility); this
> document covers the same product surface in a more expository, less dense style.

MCPlica turns an existing API (described by an OpenAPI 3.x document or an API Inventory v1 file)
into a deployed **MCP server** — a hosted endpoint that AI agents can call as a set of tools,
without hand-writing an MCP integration.

**Key objects:**

- **Project** — one API product. Has a name, a DNS-safe hostname slug, an upstream base URL, and
  its own sources, credentials, builds, and deployments.
- **Source** — an uploaded or URL-fetched OpenAPI/API Inventory document (executable) or a
  documentation file (context-only, never produces tools). Sources are versioned; each new version
  is immutable.
- **Build** — a deterministic, immutable compilation of a project's current source versions into
  an MCP tool manifest. Builds parse, index, analyze, compile, and validate asynchronously; a
  build's operations and schemas come from source truth, and OpenRouter (if configured) may only
  enrich descriptions, never invent or alter executable fields.
- **Deployment** — a running MCP runtime serving one build. Deploying replaces the active runtime
  only after the new one passes a health check; a failed replacement leaves the previous healthy
  deployment untouched.

**The end-to-end workflow** is a 10-step wizard at **Projects → New project**: name the project,
attach an executable source, optionally attach documentation, resolve the upstream server,
configure upstream credentials, start a build, watch it complete, review its validation coverage,
configure inbound MCP access, then deploy. Each section below covers one part of this flow, plus
the ongoing project pages you'll use after initial setup.

## Creating a project

From **Projects → New project**, the wizard walks through 10 steps. You can leave and come back —
the URL carries `?step=N&project=<id>` and resumes at the furthest completed step.

1. **Name the API product.** Project name and a DNS-safe hostname slug (3–63 lowercase
   letters/numbers/hyphens; auto-generated from the name, editable before the project is created,
   locked after).
2. **Attach the executable source.** Upload a file or fetch from an HTTPS URL: OpenAPI 3.0/3.1 or
   API Inventory v1. This is the source of truth for every tool's method, path, schema, and auth
   requirement — invalid references here block a `READY` build.
3. **Add supplemental documentation** (optional). Documentation sources enrich tool descriptions
   but can never create executable tools; skippable.
4. **Select the upstream API server.** Set a resolution base URL (only needed for relative source
   URLs) and, if a source operation has multiple candidate servers, pick which one it resolves
   against. This is the allowlisted transport destination — MCP callers cannot override it with
   tool arguments.
5. **Configure upstream authentication.** Map a credential to each source-declared security
   scheme the runtime supports (bearer, API key in header/query, basic, OAuth2 client credentials,
   or static headers). Secrets are accepted once, encrypted, and never redisplayed. Credential
   values and binding are administrator-only — non-admins see mapping status only and must ask an
   admin to complete it.
6. **Create an immutable build.** Starts the build; it binds the exact current source versions so
   the result never drifts.
7. **Build progress.** Live status without a page reload. A `FAILED` build shows an error code and
   summary; a `CANCELLED` build cannot become deployable.
8. **Coverage and blocking findings.** A build must reach 100% operation coverage (after any
   explicit exclusions) with zero blocking findings to proceed.
9. **Protect the published MCP endpoint.** Configure inbound authentication for the MCP server
   itself (independent of the upstream API credentials from step 5) — static high-entropy bearer
   tokens are the supported baseline. Administrator-only; non-admins see status only.
10. **Deploy the validated build.** Deploys a separate runtime that must pass a health check
    before it becomes the active one; a failed replacement leaves the previous healthy deployment
    running untouched.

## Managing sources

The **Sources** tab (`/projects/:id/sources`) lists every source attached to a project, 25 per
page.

Each source card shows its kind (OpenAPI / API Inventory / documentation), origin (upload or URL),
health (`valid` / `invalid` / `missing`/pending), and whether it's the **Primary** executable
source. From a card you can:

- **Refresh** — re-fetch a URL-origin source's latest content.
- **Make primary** — promote a non-primary executable source (a project has exactly one primary
  executable source at a time).
- **Add version** — upload a new immutable version of an existing source; each version is
  content-hashed and never mutated after creation.
- **View version history** — expand to see prior versions and their metadata.
- **Delete** — removes the source, after a confirmation prompt. Sources referenced by an existing
  immutable build are protected and cannot be deleted.

Use **Add source** to attach a new one (name, kind, and either a file upload or an HTTPS URL).
Source names are not currently enforced as unique per project — adding a source with the same name
as an existing one creates a separate, independent source entry rather than a new version of the
existing one. Use distinct names to avoid confusion.

## Configuring tools

The **Tools** tab (`/projects/:id/tools`) lists every operation from a selected build's immutable
snapshot — pick which build to inspect from the dropdown; it defaults to the currently
active/served build. Search by operation, path, or tool name; filter by HTTP method or exclusion
status (currently included/excluded, excluded in this specific build, or changed since this
build).

Each operation card shows its generated tool name, source-derived description, any AI-enriched
description with a confidence score, and (expandable) its input schema, upstream authentication
mapping, and provenance.

**Excluding an operation** requires a written reason (5+ characters) — no operation can disappear
from a manifest silently. Excluding or restoring an operation only changes the *current policy*
for the *next* build; the selected build's evidence snapshot never changes retroactively. If the
current policy differs from the selected build's snapshot, a banner shows how many operations
changed and offers a **Rebuild** button to apply the new policy.

## Documentation sources

The **Documentation** tab (`/projects/:id/documentation`) lists only the project's
documentation-kind sources (added in wizard step 3 or from the Sources tab). Each card shows
format and version date, plus an expandable **indexing evidence** panel with indexed chunk count,
embedding model, vector dimensions, and a sanitized markdown preview of the content — embedding
vectors themselves are never exposed. If a project has no documentation sources, this tab shows an
empty state linking back to Sources to add one.

Documentation is indexed for retrieval during a build's AI enrichment step; it can enrich tool
descriptions but can never define or alter executable behavior.

## Mapping credentials

The **Credentials** tab (`/projects/:id/credentials`) is administrator-only — everyone else sees a
notice to ask an admin. It manages upstream API credentials (the secrets your MCP server uses to
call *your* API), separate from MCP inbound access.

Each credential shows its scheme type, bound source security scheme, created/last-rotated dates,
and a runtime status: **Configured**, **Incomplete**, **Runtime update pending**, **Runtime update
failed**, or **Revoked and effective**. Secret values are write-only — accepted once, encrypted,
and never redisplayed or recoverable through the UI.

- **Add credential** — bind a new credential to a discovered source security scheme (bearer, API
  key header/query, basic, OAuth2 client credentials, or static headers).
- **Rotate** — replace the secret value only; the source binding, API parameter, OAuth scope, and
  token method are immutable once set (create a new credential and build to remap those).
- **Revoke** — may prevent new deployments and can require replacing or stopping an active
  runtime; confirm only after coordinating that.

## Building and validating

The **Builds** tab (`/projects/:id/builds`) lists every build, newest results appended as they
complete, with status, trigger (manual/rebuild/review), manifest hash, and creation date. Only one
build can be active per project at a time — **Review**, **Rebuild**, and **New build** are all
disabled while one is in flight.

- **New build** — a fresh build from current source versions.
- **Rebuild** — a new build applying the current tool-exclusion policy (see Configuring tools).
- **Review** — requests a build for inspection without necessarily deploying it.

Opening a build (**Inspect**) shows live progress for an active build, then for a completed one:
the validation report (coverage %, blocking findings), a diff against the previous build, the
compiled manifest (downloadable as JSON), a per-operation AI enrichment run log, and export as a
zip. An active build can be cancelled; a cancelled build can never become deployable.

**Validation** requires 100% operation coverage (after explicit exclusions) and zero blocking
findings before a build can proceed to deployment.

## Deploying

The **Deployment** tab (`/projects/:id/deployment`) covers three things: the current runtime,
deploying a build, and inbound MCP authentication.

**Current runtime** shows endpoint URL, health, deployed build, image digest, and manifest hash,
with **Restart**, **Stop**, and **Copy endpoint** actions. Deploying always uses
health-before-switch: a new runtime must pass its health check before it replaces the active one,
so a failed replacement never takes down a working deployment.

**Deploying a build** — pick any `READY` build from the dropdown and deploy it. Deployment stays
blocked until inbound MCP access is configured.

**Inbound MCP access** is separate from the upstream credentials configured earlier — it protects
the MCP endpoint itself, not your API. Two modes (admin-only to configure):

- **Static bearer** — create named access tokens; a token's value is shown exactly once at
  creation, never again. Rotate a token to replace its value while keeping a configurable overlap
  window (0–900s) so in-flight clients don't break; revoke to invalidate immediately.
- **External OAuth/OIDC** — issuer URL, audiences, required scopes, and optionally a JWKS URL and
  allowed signing algorithms.

A third mode, **Disabled (development only)**, exists but is explicitly forbidden for any
internet-exposed or production endpoint — the UI shows a warning banner whenever it's active.

**Deployment history** lists every deployment with build, status, and health; a past healthy
deployment can be **rolled back to** — rollback creates a new deployment rather than mutating
history.

## Project settings

The **Settings** tab (`/projects/:id/settings`) has two cards.

**Project identity and server** — edit name, upstream base URL, and description. The slug is
fixed after the project is created (shown but not editable).

**Lifecycle controls** — enable/disable the project (disabling stops new lifecycle work without
silently orphaning running resources; requires the lifecycle-management permission) and, for users
with delete permission, a **Delete project** danger zone: type the project's slug to confirm, and
deletion is blocked while an active deployment still exists.

## Cross-project views

Outside any single project, the top-level nav has:

- **Dashboard** (`/`) — installation-wide metrics, system readiness, and recent builds across all
  projects.
- **Projects** (`/projects`) — every project, searchable; each one owns its own source set,
  builds, credentials, hostname, and runtime lifecycle. **New project** starts the wizard from
  here.
- **Builds** (`/builds`) — installation-wide immutable build history across all projects; filter
  here, then jump into a project to inspect its exact evidence.
- **Deployments** (`/deployments`) — pick a project to inspect its endpoint, health, deployed
  build reference, access mode, history, and lifecycle controls (this is a project picker, not a
  merged cross-project deployment list).
- **Activity** (`/activity`, admin-only) — durable control-plane security and lifecycle events
  across the installation; secret values and raw sensitive payloads are never shown.

## Administrator settings

**Settings** (`/settings`) is visible to everyone (Builders can inspect non-secret values; only
admins can change them) and links to three admin-only sub-pages, plus an operational limits panel:

- **Providers** (`/settings/providers`) — connect OpenRouter, securely save/rotate its API key,
  and test live reachability.
- **Models** (`/settings/models`) — select compatible analysis, validation, and embedding models
  from the live provider catalog.
- **Users and roles** (`/settings/users`) — create installation users, assign Admin or Builder
  roles, and disable access (no public registration exists).
- **Usage** (`/settings/usage`) — a per-model AI usage and cost counter, showing call count,
  total tokens, and total cost per model, drawn from the build AI-run history across all projects.
- **Operational limits** — MCP base domain, build concurrency, max upload bytes, max
  operations/project, max document chunks/project, build retention count, source version retention
  days, and a **Builders may deploy** toggle (when off, deployment controls fail closed for the
  Builder role). Live build-admission telemetry (configured limit, effective permits, waiting
  builds) is shown alongside.

This page also shows installation-wide dependency readiness (Postgres, Redis, Milvus, etc.) and
states plainly that no product telemetry is sent to the MCPlica maintainer, and that OpenRouter
receives only configured, bounded build context — never credentials.
