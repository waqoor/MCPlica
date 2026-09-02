# Control-plane API guide

The FastAPI document served at `/openapi.json` and the tracked root `openapi.json` are the
machine-readable contract. [The v1 inventory](api-inventory-v1.md) summarizes every route family
and authorization level. Product routes use `/api/v1`; `/metrics` is a separately protected
operational route.

## Base URLs and discovery

Local defaults are `http://localhost:8000/api/v1` for direct API access and
`http://localhost:8080/api/v1` through the frontend proxy. Production uses the exact HTTPS API
domain configured in `API_DOMAIN`. Liveness and readiness do not require authentication:

```bash
curl --fail --silent --show-error http://localhost:8000/api/v1/health
curl --fail --silent --show-error http://localhost:8000/api/v1/ready
curl --fail --silent --show-error http://localhost:8000/openapi.json -o openapi.json
```

The health payload reports the running product version. Readiness distinguishes core
PostgreSQL/Redis/artifact/queue failure from degraded Milvus/OpenRouter build capability.

## Provider and model settings

Administrators configure the build-time provider through the canonical v1 routes:

- `PUT /api/v1/settings/openrouter` accepts a new API key and returns only non-secret model
  settings. The normalized key is encrypted at rest and is never returned by a read endpoint.
- `POST /api/v1/settings/openrouter/test` performs a live authenticated OpenRouter model-catalog
  request and returns a bounded success/failure message; it does not invoke a project upstream.
- `GET/PUT /api/v1/settings/models` reads or changes the three required model roles and the
  documentation-processing policy.
- `GET /api/v1/settings/models/catalog` exposes compatible capabilities from the live provider.

The provider API root is an installation environment boundary and defaults to
`https://openrouter.ai/api/v1`. `OPENROUTER_SITE_URL`, when present, is sent only as attribution
metadata. The UI exposes key rotation and testing under `/settings/providers` and model selection
under `/settings/models`; it never treats a browser field as credential authority.

## Browser authentication and CSRF

The control plane uses secure HTTP-only session/refresh cookies. State-changing requests require
the matching CSRF cookie value in `X-CSRF-Token`; API authorization is enforced by user role.
Use the web UI or an HTTP client that preserves its private cookie jar. Do not place passwords,
cookies, CSRF values, one-time MCP tokens, or upstream credentials in shell history, URLs, example
files, screenshots, or tickets.

Login is rate-limited. Secret creation and rotation inputs are write-only; ordinary reads return
descriptors, prefixes, and status rather than plaintext. MCP access tokens are returned once at
issuance/rotation and must be transferred directly to the client secret store.

## Requests, responses, and long-running work

- JSON errors use a stable code, message, optional structured details, and request ID. Branch on
  the code/status, not English text.
- List APIs use bounded `page`/`page_size` pagination. Do not fetch unbounded histories or fan out
  project-scoped endpoints in the browser.
- Build and deployment creation returns `202`. Poll bounded status endpoints or use their
  server-sent event stream until a terminal state; reconnect with backoff and abort on navigation.
- Uploads and remote responses are size/time bounded. A rejected partial upload or fetch is not an
  immutable source version.
- Manifest, validation, export, diff, operation, and AI-run evidence is tied to one immutable Build.
  Never combine fields from different build IDs.

## Contract-change policy

FastAPI models are authoritative. Any route/schema change must regenerate root `openapi.json`,
frontend TypeScript/Zod clients, affected shared JSON Schemas/fixtures, documentation, and tests in
the same pull request. Run `make api-contract` to regenerate and `make api-contract-check` to verify
drift. Additive changes remain under `/api/v1`; a breaking change requires a SemVer-major decision
and migration plan, not a parallel ad hoc endpoint.
