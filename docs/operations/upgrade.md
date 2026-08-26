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
docker compose --env-file .env -f infra/compose.yaml -f infra/compose.production.yaml run --rm api alembic -c ../migrations/alembic.ini upgrade head
docker compose --env-file .env -f infra/compose.yaml -f infra/compose.production.yaml up -d --no-build api frontend builder-worker deployment-worker
```

Verify liveness, readiness, browser authentication/CSRF, queue consumption, and an existing runtime before resuming work. New compiler/runtime versions create new builds; do not mutate an artifact already attached to a deployment.

## Roll back

Application rollback is safe only while the older code understands the current schema. If migrations are backward-compatible, restore previous image digests and redeploy. If not, enter maintenance mode and restore the pre-upgrade database/artifact/secret set as one recovery point. Never run a destructive Alembic downgrade unless that exact downgrade was reviewed and rehearsed.

Project deployment rollback is separate: use the recorded target deployment in the UI/API. The backend creates a new deployment from its immutable READY build and health-checks it; it does not rewrite history.
