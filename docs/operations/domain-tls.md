# Production domains and TLS

The base Compose file is a loopback-bound development topology. Production must use `infra/compose.production.yaml`, real DNS, HTTPS, immutable release image digests, and a protected host runtime root.

## DNS and firewall

Create A/AAAA records for the UI domain, API domain, and wildcard MCP domain, for example:

- `mcplica.example.com`
- `api.mcplica.example.com`
- `*.mcp.example.com`

Point them to the Traefik host. Permit inbound TCP 80 only for HTTPS redirection/challenge and TCP 443 for service traffic. Do not publish PostgreSQL, Redis, Milvus, MinIO, etcd, the Docker socket, or the Traefik dashboard.

## Required production values

Set `UI_DOMAIN`, `API_DOMAIN`, `MCP_DOMAIN`, and `ACME_EMAIL`. Set backend, frontend, and runtime images to the exact `image@sha256:digest` values in a verified GitHub release. Set `RUNTIME_HOST_ROOT` to a dedicated absolute Docker-host directory and keep `RUNTIME_WORKER_ROOT=/runtime-host`:

```bash
sudo install -d -o 10001 -g 10001 -m 0750 /var/lib/mcplica/runtime
chmod 0600 .env
```

Compose mounts that host directory at the deployment-worker root. The deployment worker alone receives the Docker socket and writable mount. The API and builder-worker containers must not receive either deployment capability.

## Validate and start

```bash
docker compose --env-file .env -f infra/compose.yaml -f infra/compose.production.yaml config --quiet
docker compose --env-file .env -f infra/compose.yaml -f infra/compose.production.yaml pull
docker compose --env-file .env -f infra/compose.yaml -f infra/compose.production.yaml up -d --no-build
```

The override disables the dashboard, redirects HTTP to HTTPS, enables the `websecure` entrypoint, and obtains certificates with the ACME TLS challenge. Protect the ACME volume and include it in host recovery planning; private keys must not be copied into the repository.

The TLS challenge issues certificates for concrete hostnames. If the installation uses a wildcard MCP certificate, switch the resolver to a reviewed DNS-01 provider and supply that provider's credential through the host secret store, never a Compose label or committed file. Restrict the deployment worker and Traefik Docker API surface with an authorization/socket proxy where the host platform supports it; the public API, builder worker, and every MCP runtime remain socket-free.

## Acceptance checks

```bash
curl --fail --silent --show-error https://mcplica.example.com/healthz
curl --fail --silent --show-error https://api.mcplica.example.com/api/v1/health
curl --fail --silent --show-error https://api.mcplica.example.com/api/v1/ready
openssl s_client -connect mcplica.example.com:443 -servername mcplica.example.com </dev/null
```

Verify a browser login, CSRF-protected state change, one project runtime, and its authenticated `/mcp` endpoint. Confirm HTTP redirects, the certificate chain and hostname are valid, cookies are `Secure`/`HttpOnly` as designed, the dashboard is unavailable, and an unknown hostname is not routed to a project.

Wildcard DNS and TLS do not authorize a runtime. Traefik labels are created only for a recorded deployment, while inbound MCP authentication and runtime host validation remain mandatory.
