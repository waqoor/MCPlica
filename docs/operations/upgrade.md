# Upgrade and rollback

Upgrade only between verified releases and never by pulling mutable `latest` tags.

## Preflight

1. Read release notes, schema changes, security notes, and runtime compatibility declarations.
2. Verify release checksums, SBOMs, signatures, and image digests using `../release/release-process.md`.
3. Complete a current backup and confirm the most recent restore drill remains applicable.
4. Export the current Compose render, database revision, active deployment/image/manifest digests, and health evidence.
5. Test the upgrade on a restored non-production copy, including login, source parsing, build validation, credential connection, deployment, MCP invocation, and rollback.

## Apply

Pause new builds/deployments, stop both workers, pull the new digest-pinned images, and run database migrations as an explicit job:

```bash
docker compose --env-file .env -f infra/compose.yaml -f infra/compose.production.yaml run --rm migrate
docker compose --env-file .env -f infra/compose.yaml -f infra/compose.production.yaml up -d --no-build api frontend builder-worker deployment-worker
```

Verify liveness, readiness, browser authentication/CSRF, queue consumption, and an existing runtime before resuming work. New compiler/runtime versions create new builds; do not mutate an artifact already attached to a deployment.

## Roll back

Application rollback is safe only while the older code understands the current schema. If migrations are backward-compatible, restore previous image digests and redeploy. If not, enter maintenance mode and restore the pre-upgrade database/artifact/secret set as one recovery point. Never run a destructive Alembic downgrade unless that exact downgrade was reviewed and rehearsed.

Project deployment rollback is separate: use the recorded target deployment in the UI/API. The backend creates a new deployment from its immutable READY build and health-checks it; it does not rewrite history.

## 2026-09-02 foundation consistency migrations

This change advances Alembic from `0020` to `0025`. Stop the API and both workers
before running the migration so no pre-fencing owner can continue external work.
Keep PostgreSQL, artifacts, runtime files, and Milvus volumes together in the backup.

- `0021` adds explicit current-source selection/observation state and freezes executable
  metadata on Build/source bindings. It backfills the newest known version as current but
  marks historical Build metadata untrustworthy because prior roles/aliases cannot be proven.
  Rebuild before newly activating one of those historical Builds. Its downgrade deliberately
  refuses when a source has been restored away from creation-time latest; first restore a
  pre-`0021`-representable selection or retain the migration.
- `0022` adds runtime-command execution tokens and ownership constraints. Any command that was
  dispatched/running without a token is requeued for a fresh fenced claim; downgrade likewise
  requeues token-bearing live attempts before dropping the column.
- `0023` persists deployment intent and backfills existing rows as `normal`.
- `0024` fences cleanup attempts. Pre-fencing running cleanup targets become due retries so an
  unowned external deletion is never treated as current work.
- `0025` records the accepted Build execution token on new index generations. Existing null-token
  generations retain legacy retrieval semantics; rebuild them to obtain attempt-scoped Milvus
  rows. Do not rewrite immutable historical artifacts or bulk-delete shared collections.

The migration rehearsal must run `upgrade head`, `alembic check`, a safe
`0025→0020→0025` round trip on empty/new-state-free data, and an explicit rejection case for an
A→B→A restored source. After upgrade, reconcile pending runtime commands and cleanup targets,
then verify exact active Build/container identity before resuming either worker.

## 2026-09-01 vector-isolation and Docker corrections

New documentation and semantic vector rows include project, generation, and source
version in their primary-key identity. Existing content hashes and embedding-cache
records remain reusable. This correction prevents new cross-scope overwrites; it
cannot recreate historical rows already lost. Create a new build for each affected
project using its retained source versions, inspect its retrieval/validation results,
and deploy through the existing lifecycle. Keep old immutable build artifacts and
rollback evidence. Never purge a shared collection as an upgrade step.

The runtime now rejects media mismatches in a declared exact/class response instead
of accepting them through a less-specific default. Correct an inaccurate API source
or upstream response rather than suppressing the contract error. Updating control-
plane images alone does not replace already running project containers: deploy the
intended compatible generic runtime through the normal project lifecycle.

Keep the configured edge-network name unchanged during an ordinary upgrade. Changing
`TRAEFIK_NETWORK` requires coordinated recreation of its Compose consumers; API/UI
routing labels and the production provider use the configured value. Preserve all
volumes and the runtime host root. Docker build inputs now exclude private runtime
and environment/key files; custom private directories must remain outside the source
checkout or have an explicit reviewed exclusion.

Fresh checks and exact evidence are in
`../evidence/post-merge-validation-2026-09-01.md`. These changes require no database
migration beyond the existing migration head and do not establish a live production
rollout or a completed backup restoration.
