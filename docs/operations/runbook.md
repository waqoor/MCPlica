# Operations and incident runbook

## Observe before changing state

Check `GET /api/v1/health`, then `GET /api/v1/ready`, Compose/container health, both worker queue depths, disk/inodes, database connections, and the affected request ID. Treat a core-ready response with `milvus=false` or `openrouter=false` as degraded Builder capability, not full recovery. Preserve sanitized logs and deployment/build IDs. Do not paste manifests, request bodies, cookies, bearer tokens, OpenRouter keys, upstream headers, or secret-bundle paths into tickets.

## Common conditions

| Symptom                   | Checks                                                                                    | Safe response                                                                                  |
| ------------------------- | ----------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| UI unavailable            | frontend health, Traefik route/certificate, API health                                    | Keep runtimes untouched; restore UI/ingress from pinned image                                  |
| API live but not ready    | readiness dependency map, PostgreSQL, Redis                                               | Stop mutations and both workers; restore the authoritative dependency                          |
| Builds queued             | Redis/RQ builder worker, build queue, timeout, OpenRouter/Milvus status, disk             | Do not duplicate jobs manually; recover the builder worker and use canonical retry/cancel flow |
| Deployments queued        | Redis/RQ deployment worker, deployment queue, Docker daemon/socket, runtime-host capacity | Keep the active runtime; recover the deployment worker and use the canonical retry/stop flow   |
| Deployment activating    | Candidate edge identity, superseded `RUNNING`/`STOPPING` rows and containers, worker logs | Retry the same deployment job; do not provision another candidate or mark it `RUNNING` manually |
| Build failed              | build stage, stable error code, validation findings, source version                       | Fix source/config and create a new build; never mark failed output READY                       |
| Runtime unhealthy         | deployment events, container health, manifest/image digest, upstream DNS/TLS              | Keep/restore prior healthy deployment; do not bypass health-before-switch                      |
| Authentication failures   | clock, cookie flags/origin, CSRF, user status, MCP token expiry/OIDC claims               | Rotate/re-authenticate through normal flow; never reveal stored secret values                  |
| Suspected secret exposure | scope, logs/artifacts, access audit                                                       | Isolate, revoke/rotate, preserve evidence, privately notify maintainer                         |

## Incident priorities

For active compromise, first prevent further access without destroying evidence: remove public routing or isolate the host, stop both workers and runtime mutations, preserve logs/metadata, and rotate exposed external credentials from a trusted system. Do not delete affected containers, volumes, audit rows, or logs until evidence and recovery copies exist.

Use private vulnerability reporting for product defects. Record timeline, affected projects/builds/deployments, data/secret exposure assessment, containment, eradication, recovery proof, and follow-up owners. Public disclosure is coordinated under `SECURITY.md`.

## Health and rollback acceptance

A recovered service must pass API health/readiness, both worker-registration health
checks, Traefik ping and an exact Build/Deployment `/readyz` edge probe, browser login
and one CSRF-protected mutation, queue processing, source retrieval policy, a 100%
validation gate for a known fixture, authenticated MCP invocation, log redaction review,
and backup continuity. "Container running" alone is not recovery.
