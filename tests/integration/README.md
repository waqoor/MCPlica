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

The `postgres` marker suite is mandatory for foundation ownership changes. It uses
real transactions and independent connections to prove A→B→A current-source selection,
concurrent observation ordering, dead-owner cancellation recovery, stale Build-result
rejection, STOP→DEPLOY predecessor ordering, final-token STOP behavior, security refresh
against the exact active Build, runtime project-lock serialization, and stale command
finalization rejection. `test_schema_drift_postgres.py` also creates isolated temporary
databases for the `0025→0020→0025` migration rehearsal and the intentional `0021`
downgrade rejection when restored source selection cannot be represented by the old schema.
Mock-only coverage is not accepted for these invariants.

The remaining `issues_002.md` hardening is exercised by the normal component
suites: request-size/spool bounds, shared authentication selection, schema-only
reference materialization and RFC 6901 traversal, DOCX ordering, semantic-output
validation, total HTTP deadlines, streamed provider caps and attempt accounting,
bounded management pagination, safe structured logs, secret-key rotation, and
OAuth/OIDC edge cases. The frontend contract/unit suites consume the regenerated
OpenAPI pages, while the browser and Compose acceptance below verify the integrated
runtime rather than replacing those focused regressions.

## Full clean-install acceptance

Use a **fresh clone on a disposable Linux Docker host**, with no existing selected environment
file, MCPlica Compose project, active runtimes, or retained volumes. The test changes model
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

For a second disposable project on a development host, select a separate ignored environment
file, project name, host ports, runtime root, and network names. The preparation helper writes the
isolated values without replacing the retained `.env`:

```bash
python tests/integration/prepare_compose.py --output .env.v1rc --project-name mcplica-v1rc --api-port 18000 --frontend-port 18080 --edge-tls-port 18443
export MCPLICA_ENV_FILE="$(pwd)/.env.v1rc"
docker compose --env-file "$MCPLICA_ENV_FILE" -f infra/compose.yaml config --quiet
```

Pass `--api-base http://127.0.0.1:18080/api/v1` to the workflow in that isolated case. The
canonical HTTP edge still requires host port 80 and fixture ports 9009/9010 must be free; stop a
conflicting development proxy without deleting its volumes, then restore it after the test. Never
point the helper or harness at retained volumes or a production environment.

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

`prepare_compose.py --project-name <name>` persists that name as
`COMPOSE_PROJECT_NAME` and writes `CONTROL_PLANE_ENV_FILE` relative to the canonical
Compose file. Every later Compose command and every backend container therefore
target the same disposable project and configuration. Use a unique name for
side-by-side local validation; do not reuse the name of an installation you intend
to retain.

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

CI preserves `workflow.json`, final `services.json`, and bounded/redacted `compose.log` in the
`compose-validation` artifact associated with the workflow's exact commit. Browser traces,
screenshots, and videos are deliberately disabled in public CI because they can capture session
cookies, form values, response bodies, or ephemeral credentials. Both one-shot services must exit
0 and all 11 long-running
services must be healthy before and after acceptance. Inspect failures rather than
removing checks or marking skipped steps passed.

CI cleanup is scoped to its disposable runner. Removing volumes destroys data; do
not copy that cleanup command to a persistent host. Following an interrupted local
exercise, inspect service states and restore the stopped services before any further
use. Never run this harness against an existing development or production deployment.

## Additional post-merge acceptance

The disposable configuration selects a non-default `TRAEFIK_NETWORK` to exercise
actual routing through the configured edge. The Docker CI job additionally runs:

```bash
python tests/integration/docker_context_check.py
docker compose --env-file .env -f infra/compose.yaml exec -T -e RUN_DOCKER_INTEGRATION=1 builder-worker python < tests/integration/vector_isolation_check.py
```

The first command uses a temporary synthetic context and Docker's own exclusion
engine, without reading real secrets. It verifies runtime/private files are not
copied and required source/example files remain present. The second uses the real
Milvus client/store and a unique disposable collection to exercise duplicate content
across projects/generations, idempotent upserts, and scoped deletion. Run only in the
explicit disposable acceptance installation; it rejects production settings.

Fixture cancellation checks deterministically simulate a transport returning after
consuming task cancellation. The fixture must propagate owner cancellation and
release only its owned listener/task; intermittent passing alone is not evidence
of a corrected race. Focused schema, canonicalization, chunk-identity, Compose,
Makefile, and response-dispatch regressions are included in the normal component
suites. None of these checks runs during ordinary deployment startup.
