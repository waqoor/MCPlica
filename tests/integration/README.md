# Cross-service acceptance

The canonical acceptance runs against `infra/compose.yaml`, not an alternative app
stack. Real components include API, database, Redis/RQ, Milvus/etcd/MinIO, workers,
runtime validator, Docker-created project runtimes, Traefik, and the browser UI.
Only the OpenRouter and example upstream HTTP APIs are deterministic local fixtures.
Passing these tests does not prove commercial model behavior or live production TLS.

## Focused regressions

```bash
uv run --project backend --frozen --extra dev pytest backend/tests/test_compose_configuration.py tests/integration/test_fixture_server.py
```

Fixture lifecycle checks use real HTTP connections and restart the same port. They
also cover a port owned by another process, duplicate start, unhealthy startup, and
cancellation. Fixture failures release only owned resources; no unrelated process
is killed and no active listener is shared.

## Full clean-install acceptance

Use a **fresh clone on a disposable Linux Docker host**, with no existing `.env`,
MCPlica Compose project, active runtimes, or retained volumes. The test changes model
settings, creates projects/secrets, stops services, replaces runtimes, and recreates
containers. It refuses `ENV=production` and requires `RUN_DOCKER_INTEGRATION=1`.
This is a separate verification operation, never a deployment startup step.

```bash
uv sync --project backend --frozen --extra dev
python tests/integration/prepare_compose.py
```

Set `E2E_UPSTREAM_BASE_URL` to the exact bridge-gateway URL printed by preparation;
GitHub Actions exports it automatically. Do not substitute Desktop-only DNS on Linux.
The fixtures own host ports 9009 and 9010; the canonical test UI uses 8080 and the
HTTP edge uses 80. An occupied fixture port fails without disturbing its owner.

```bash
docker compose --env-file .env -f infra/compose.yaml config --quiet
PYTHONPATH=backend uv run --project backend --frozen --extra dev python tests/integration/production_config_check.py
docker compose --env-file .env -f infra/compose.yaml build api runtime-validator frontend
docker compose --env-file .env -f infra/compose.yaml up --no-build --detach --wait --wait-timeout 300
python tests/integration/compose_evidence.py --check
docker compose --env-file .env -f infra/compose.yaml exec -T api python -m app.cli.ensure_development_admin
RUN_DOCKER_INTEGRATION=1 PYTHONPATH=backend:tests/integration uv run --project backend --frozen --extra dev python tests/integration/full_stack_workflow.py --api-base http://127.0.0.1:8080/api/v1 --report output/compose-validation/workflow.json
```

The workflow covers login/CSRF, executable and documentation ingestion, credentials,
indexing/retrieval, AI enrichment/validation, immutable manifests/exports, one-time
MCP access tokens, four HTTP-method mappings, runtime calls during builder/provider
outage, recovery, changed-source rebuild/diff, redeployment, rollback, and persisted
active state plus MCP execution after database/cache/control-plane recreation.
The persistence exercise retains named volumes; it is not a backup/restore drill.

The existing CI also runs `backend/tests/integration/test_dynamic_runtime_docker.py`
with its configured isolated runtime paths, then the actual UI:

```bash
cd frontend
corepack enable
pnpm install --frozen-lockfile
pnpm exec playwright install --with-deps chromium
E2E_LIVE=1 E2E_BASE_URL=http://127.0.0.1:8080 pnpm exec playwright test e2e/live-stack.spec.ts --project=chromium
cd ..
python tests/integration/compose_evidence.py --check
```

The default cross-browser suite uses controlled API fixtures; the separate
`E2E_LIVE=1` test proves a browser session against the actual Compose control plane.
Do not present the mocked suite alone as proof of backend integration.

## Evidence and cleanup

CI preserves `workflow.json`, final `services.json`, bounded/redacted `compose.log`,
and browser diagnostics in the `compose-validation` artifact associated with the
workflow's exact commit. Both one-shot services must exit 0 and all 11 long-running
services must be healthy before and after acceptance. Inspect failures rather than
removing checks or marking skipped steps passed.

CI cleanup is scoped to its disposable runner. Removing volumes destroys data; do
not copy that cleanup command to a persistent host. Following an interrupted local
exercise, inspect service states and restore the stopped services before any further
use. Never run this harness against an existing development or production deployment.
