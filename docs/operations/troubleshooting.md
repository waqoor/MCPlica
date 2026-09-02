# Troubleshooting

Start with evidence, not deletion or manual database/container state changes. Preserve request,
project, build, deployment, and cleanup IDs; sanitize logs before sharing them.

## First checks

```bash
docker compose --env-file .env -f infra/compose.yaml config --quiet
docker compose --env-file .env -f infra/compose.yaml ps --all
curl --fail --silent --show-error http://localhost:8000/api/v1/health
curl --fail --silent --show-error http://localhost:8000/api/v1/ready
docker compose --env-file .env -f infra/compose.yaml logs --tail=100 api builder-worker deployment-worker traefik
```

Do not print `docker compose config` for a real installation into a ticket: expanded output can
contain secrets. Do not use `down --volumes`, delete runtime files, edit status rows, or run manual
Docker replacement commands as a diagnostic shortcut.

## Common failures

| Symptom                                               | Evidence to inspect                                                          | Corrective direction                                                                                                                                                                                                                                                                                                                                                                |
| ----------------------------------------------------- | ---------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Compose reports `MCPLICA_VERSION` missing             | Existing `.env` predates v1 version authority                                | Add `MCPLICA_VERSION=1.0.0`, remove obsolete `MCP_RUNTIME_VERSION`, rerun `config --quiet`                                                                                                                                                                                                                                                                                          |
| `migrate` exits nonzero                               | Migration log, current/head revision, backup state                           | Stop API/workers, retain volumes, resolve the exact migration condition; never skip the job                                                                                                                                                                                                                                                                                         |
| Control plane shows `Degraded` while the API is ready | Readiness dependency map and **Settings > Providers** status rail            | `milvus=false` or `openrouter=false` disables Builder capability without taking down existing control-plane/runtime access. For OpenRouter, keep `OPENROUTER_BASE_URL=https://openrouter.ai/api/v1`, save/rotate a valid key, run **Test connection**, then select all three models. Do not point production at the local fixture or use `https://openrouter.ai/api` without `/v1`. |
| API returns HTTP 503 readiness                        | Readiness dependency map                                                     | Recover PostgreSQL/Redis/artifact/queue core dependencies before mutations; optional provider recovery alone cannot restore core readiness                                                                                                                                                                                                                                          |
| Worker unhealthy or work remains queued               | Worker health, queue name, Redis, lease/token fields                         | Restore the same worker/queue and let fenced retry logic reclaim; do not duplicate jobs                                                                                                                                                                                                                                                                                             |
| Runtime route returns Traefik 404/503                 | Deployment status, edge network, labels, exact `/readyz` host probe          | Rerun canonical Compose `up` so deployment-worker startup reconciliation can restore an activation-proven active route. If the recorded container identity is missing or unhealthy, use the recorded restart/redeploy lifecycle; do not attach arbitrary containers.                                                                                                                   |
| Build validation fails                                | Immutable Build validation report/source pointers                            | Correct source/config and create a new Build; never edit or force READY output                                                                                                                                                                                                                                                                                                      |
| MCP returns 401/403                                   | Access status, token expiry/revocation or OIDC issuer/audience/scope/clock   | Rotate/reconfigure through MCP access; never enable production unauthenticated mode                                                                                                                                                                                                                                                                                                 |
| MCP schema/call fails                                 | Deployed build ID, advertised schema, sanitized upstream status/content type | Send a schema-valid call or correct/rebuild the source contract; do not bypass runtime validation                                                                                                                                                                                                                                                                                   |
| New config is ignored                                 | Whether `restart` was used                                                   | Run `up --detach` with the same env/Compose arguments so containers are recreated                                                                                                                                                                                                                                                                                                   |
| Disk/runtime-root permission failure                  | Free space/inodes, absolute host path, UID/GID 10001                         | Restore capacity/ownership and rerun `runtime-init`; do not relax secret permissions                                                                                                                                                                                                                                                                                                |

## Migration and rollback boundaries

The v1 migration head is `0025`. A blank/new-state-free database supports the documented
`0025 -> 0020 -> 0025` rehearsal. Migration `0021` intentionally refuses downgrade when a source
selection cannot be represented by the older schema. Preserve data and follow the release upgrade
guide; do not turn a deliberate refusal into a destructive downgrade.

Application-image rollback and project-runtime rollback are different. Image rollback is allowed
only when the older code understands the current schema, otherwise restore the coordinated
pre-upgrade recovery point. Project rollback creates a new deployment from a previously proven
immutable Build and health-checks it through the normal lifecycle.

## Escalation

Follow [the operations runbook](runbook.md) for incident containment and recovery acceptance,
[backup/restore](backup-restore.md) for data recovery, [support policy](../../SUPPORT.md) for public
help, and [SECURITY.md](../../SECURITY.md) for private vulnerability reporting.
