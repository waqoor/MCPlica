# Control-plane API inventory (v1)

The live FastAPI schema at `/openapi.json` is the machine-readable contract. This inventory records the stable route families and their security intent; it must change in the same pull request as a route contract.

Product routes are under `/api/v1`. The operational `/metrics` route is deliberately outside the product OpenAPI document. JSON state mutations require an authenticated session and CSRF cookie/header match unless explicitly listed as public. Errors use a stable code/message/details/request-ID envelope. Secret create/rotate fields are write-only and never returned.

| Method and path                                                              | Authorization                     | Purpose                                                  |
| ---------------------------------------------------------------------------- | --------------------------------- | -------------------------------------------------------- |
| `GET /health`                                                                | Public                            | Process liveness only                                    |
| `GET /ready`                                                                 | Public                            | Concurrent core readiness plus AI/vector degradation map |
| `GET /metrics` (root route)                                                  | Configured bearer; required in prod | Bounded-label Prometheus operational metrics            |
| `POST /auth/login`                                                           | Public, rate limited              | Create cookie session                                    |
| `POST /auth/refresh`                                                         | Refresh cookie + CSRF             | Rotate/refresh session                                   |
| `POST /auth/logout`                                                          | Session if present + CSRF         | Revoke session and clear cookies                         |
| `GET /auth/me`                                                               | Authenticated                     | Current user identity/role                               |
| `GET/POST /users`                                                            | Admin                             | List/create local users                                  |
| `PATCH /users/{user_id}`                                                     | Admin                             | Change display name, password, role, or active state     |
| `GET/POST /projects`                                                         | Builder or admin                  | List/create projects                                     |
| `GET/PATCH /projects/{project_id}`                                           | Builder or admin                  | Read/update project                                      |
| `GET /projects/{project_id}/journey`                                         | Builder or admin                  | Reconstruct durable ten-step completion                  |
| `DELETE /projects/{project_id}`                                              | Admin                             | Return durable asynchronous cleanup job                  |
| `GET/POST /projects/{project_id}/sources`                                    | Builder or admin                  | Paginated summaries/create source metadata               |
| `POST /projects/{project_id}/sources/(upload\|url)`                         | Builder or admin                  | Atomically create source plus first version              |
| `GET /projects/{project_id}/source-configuration`                            | Builder or admin                  | Discover servers/security and readiness gaps             |
| `PATCH/DELETE /projects/{project_id}/sources/{source_id}`                    | Builder or admin                  | Update lifecycle/return cleanup job                      |
| `POST /projects/{project_id}/sources/{source_id}/versions`                   | Builder or admin                  | Stream a bounded upload into an immutable version        |
| `POST /projects/{project_id}/sources/{source_id}/refresh`                    | Builder or admin                  | Fetch a configured URL under network policy              |
| `GET /projects/{project_id}/sources/{source_id}/versions`                    | Builder or admin                  | Paginate immutable versions                              |
| `GET /source-versions/{version_id}/metadata`                                 | Builder or admin                  | Read parse/index metadata without source secret material |
| `GET /builds`                                                                | Builder or admin                  | Bounded global build list filtered by project/status     |
| `GET /build-admission`                                                       | Builder or admin                  | Inspect PostgreSQL admission leases/queue                |
| `GET/POST /projects/{project_id}/builds`                                     | Builder or admin                  | Project history/start asynchronous build                 |
| `POST /projects/{project_id}/review`                                         | Builder or admin                  | Start manual semantic review build                       |
| `POST /projects/{project_id}/rebuild`                                        | Builder or admin                  | Start canonical rebuild                                  |
| `GET /builds/{build_id}`                                                     | Builder or admin                  | Read immutable build state/evidence fields               |
| `POST /builds/{build_id}/cancel`                                             | Builder or admin                  | Request cancellation through state machine               |
| `GET /builds/{build_id}/events`                                              | Builder or admin                  | Bounded server-sent build status changes                 |
| `GET /builds/{build_id}/diff`                                                | Builder or admin                  | Read deterministic changes from the prior READY build    |
| `GET /builds/{build_id}/manifest[/download]`                                 | Builder or admin                  | Validate/view or download the raw compiled manifest       |
| `GET /builds/{build_id}/validation`                                          | Builder or admin                  | Read coverage, findings, exclusions, and source evidence |
| `GET /builds/{build_id}/export`                                              | Builder or admin                  | Download the secret-free immutable build bundle          |
| `GET /builds/{build_id}/operations`                                          | Builder or admin                  | Read compiled operation mappings and provenance          |
| `GET /builds/{build_id}/ai-runs`                                             | Builder or admin                  | Read non-chain-of-thought model run metadata             |
| `GET/POST/DELETE /projects/{project_id}/operation-exclusions[/\{exclusion_id\}]` | Builder or admin                  | Read/add/remove the current explicit exclusion policy     |
| `GET/POST /projects/{project_id}/credentials`                                | Admin                             | List non-secret descriptors/create encrypted credential  |
| `POST /projects/{project_id}/credentials/{credential_id}/rotate`             | Admin                             | Replace encrypted secret; preserve immutable auth binding |
| `DELETE /projects/{project_id}/credentials/{credential_id}`                  | Admin                             | Revoke credential without revealing it                   |
| `GET/POST /projects/{project_id}/deployments`                                | Authenticated read/admin mutation | Paginated history/create from READY build                |
| `GET /deployments/{deployment_id}`                                           | Authenticated                     | Read deployment evidence/status                          |
| `GET /deployments/{deployment_id}/events`                                    | Authenticated                     | Bounded server-sent status changes                       |
| `POST /deployments/{deployment_id}/stop`                                     | Admin                             | Stop recorded runtime                                    |
| `POST /deployments/{deployment_id}/restart`                                  | Admin                             | Restart via deployment state machine                     |
| `POST /projects/{project_id}/rollback`                                       | Admin                             | Create deployment from `target_deployment_id`            |
| `GET /projects/{project_id}/mcp-access`                                      | Authenticated                     | Read auth config and non-secret token descriptors        |
| `GET /projects/{project_id}/mcp-access/status`                               | Authenticated                     | Read builder-safe configured/effect state                |
| `PUT /projects/{project_id}/mcp-access/auth-mode`                            | Admin                             | Configure static bearer or external OIDC verifier        |
| `POST /projects/{project_id}/mcp-access/tokens`                              | Admin                             | Issue one-time plaintext token response                  |
| `POST /projects/{project_id}/mcp-access/tokens/{token_id}/rotate`            | Admin                             | Rotate with bounded overlap                              |
| `DELETE /projects/{project_id}/mcp-access/tokens/{token_id}`                 | Admin                             | Revoke token                                             |
| `GET/PATCH /settings`                                                        | Builder read/admin mutation       | Read/update bounded operational policy                   |
| `GET/PUT /settings/models`                                                   | Builder read/admin mutation       | Read/update builder-only model policy                    |
| `PUT /settings/openrouter`                                                   | Admin                             | Rotate encrypted OpenRouter key                          |
| `POST /settings/openrouter/test`                                             | Admin                             | Test provider capabilities without disclosing key        |
| `GET /settings/models/catalog`                                               | Admin                             | Read provider model capability catalog                   |
| `GET /audit`                                                                 | Admin                             | Paginated/filtered audit events                          |
| `GET /cleanup-jobs[/{job_id}]`                                               | Admin                             | Inspect durable external-cleanup progress/errors         |

The global Deployments area is a project navigator because the authoritative API exposes project-scoped deployment history, not a global deployment collection. Health, history, endpoint, authentication, and lifecycle actions remain on each project Deployment page; the browser does not fan out requests or invent an alternate aggregation path.

List endpoints that can grow must expose bounded pagination before production scale. SSE/polling clients must abort on navigation, back off or use bounded intervals, and stop after terminal state. External/source calls occur only through backend clients; browser components never call OpenRouter, Milvus, upstream APIs, or arbitrary source URLs directly.
