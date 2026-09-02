# Docker Compose deployment

`infra/compose.yaml` is the single canonical topology. `infra/compose.production.yaml` is a
production override of that topology, not a separate application architecture. Always pass the
environment and Compose files explicitly from the repository root.

## Services and startup order

The stack contains eleven long-running services plus two one-shot jobs. PostgreSQL, Redis, etcd,
MinIO, Milvus, API, runtime validator, builder worker, deployment worker, frontend, and Traefik must
be running and healthy. `migrate` and `runtime-init` must exit 0. API/workers wait for migration;
the deployment worker also waits for runtime-root ownership; the builder waits for Milvus and the
runtime validator.

Ordinary deployment never runs tests. CI or an explicitly disposable acceptance host executes
release validation before publication.

## Development lifecycle

```bash
python scripts/init_env.py
docker compose --env-file .env -f infra/compose.yaml config --quiet
docker compose --env-file .env -f infra/compose.yaml build api runtime-validator frontend
docker compose --env-file .env -f infra/compose.yaml up --no-build --detach --wait --wait-timeout 300
docker compose --env-file .env -f infra/compose.yaml exec -T api python -m app.cli.ensure_development_admin
docker compose --env-file .env -f infra/compose.yaml ps --all
```

Use `up --build`, not `restart`, after source, image, Compose, or environment changes. `restart`
does not apply changed configuration. `docker compose ... down` removes managed containers and
networks but preserves named volumes. Adding `--volumes` destroys retained Compose data and belongs
only in an explicitly disposable environment.

## Networks, ports, and runtime containers

The internal builder network holds PostgreSQL, Redis, etcd, MinIO, and Milvus without host ports.
The API and frontend publish loopback ports for development. Traefik owns edge routing. Each
deployed project runtime is created by the canonical deployment worker on a project network plus
the configured edge network; it is not a Compose service and must be managed through MCPlica.
`BUILDER_NETWORK`, `EGRESS_NETWORK`, and `TRAEFIK_NETWORK` may rename those same boundaries when a
separate disposable acceptance project must coexist on a development host; unique names do not
create a different topology.

Only the deployment worker has the writable Docker socket/runtime-root boundary. Traefik has a
read-only provider socket. API, builder worker, frontend, and project runtimes remain socket-free.

## Persistent state

Named volumes hold PostgreSQL, Redis AOF, etcd, MinIO, Milvus, and artifacts. `RUNTIME_HOST_ROOT`
is an absolute Docker-host bind path for per-project manifest/auth/secret material. Production also
persists ACME state. Back up PostgreSQL, artifacts, runtime root, keys, image digests, and relevant
index state as one coordinated recovery point; Redis alone is never authoritative.

## Production render

Production initialization deliberately leaves image variables and public-domain values blank.
Set them in a private file, using image `name@sha256:digest` references from a verified release:

```bash
python scripts/init_env.py --production --output .env.production
export MCPLICA_ENV_FILE="$(pwd)/.env.production"
docker compose --env-file "$MCPLICA_ENV_FILE" -f infra/compose.yaml -f infra/compose.production.yaml config --quiet
docker compose --env-file "$MCPLICA_ENV_FILE" -f infra/compose.yaml -f infra/compose.production.yaml pull
docker compose --env-file "$MCPLICA_ENV_FILE" -f infra/compose.yaml -f infra/compose.production.yaml up --no-build --detach --wait --wait-timeout 300
```

The override removes local builds, requires immutable application image values, enables HTTPS,
redirects HTTP, and persists certificates. A successful render proves interpolation only; it does
not prove registry access, image signatures, DNS, certificates, firewall policy, host capacity,
provider credentials, or restored data.

## Release-candidate acceptance

On a new disposable environment only, follow [the integration instructions](../../tests/integration/README.md).
The canonical harness exercises migrations, source/build/deployment state, authenticated MCP
calls, dependency outage recovery, rebuild/redeploy, rollback, and persistence through container
recreation. It refuses production mode and must never be copied into startup commands.
