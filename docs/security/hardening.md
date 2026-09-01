# Deployment hardening checklist

Use this checklist with the threat model and production Compose override. It is an acceptance gate, not a substitute for host security review.

## Host and containers

- Run a supported, patched Linux/Docker/Compose stack with disk encryption, time synchronization, restricted SSH, firewalling, and monitored storage.
- Permit the Docker socket only in the deployment worker and Traefik's read-only provider mount. Treat membership in its group as root-equivalent.
- Confirm API, builder worker, deployment worker, frontend, and project runtimes run non-root, drop all capabilities, set `no-new-privileges`, use read-only roots/tmpfs, and have health/resource limits.
- Keep the build and deployment queues distinct. The builder worker must not receive the Docker socket or runtime-host mount; the deployment worker must not consume build jobs.
- Mount runtime manifests and secret bundles read-only from the dedicated host root; reject permissive secret-file modes.
- Keep private runtime/environment/key material outside image build inputs. The root `.dockerignore` excludes `.runtime`, nested private `.env` files, and common private key/certificate paths. Keep custom private roots outside the source checkout; exclusion patterns do not detect secrets embedded in source files.
- Validate build-context exclusions with `tests/integration/docker_context_check.py` using its synthetic files, never actual credentials.
- Keep PostgreSQL, Redis, Milvus, MinIO, and etcd on internal/private networks. Publish no development dashboard.

## Identity and secrets

- Use unique high-entropy encryption, signing, refresh-pepper, database, MinIO, OpenRouter, upstream, and MCP-access values in an external secret manager.
- Remove the bootstrap secret after first-admin creation. Disable dormant users and review admin assignments.
- Keep builders unable to deploy unless the installation explicitly accepts that policy.
- Use static MCP bearer tokens with expiration/rotation or a reviewed OIDC issuer, exact audience, algorithms, JWKS, and scopes. Never pass tokens in URLs.
- Rehearse key/session/token rotation and encrypted credential restore without logging plaintext.

## Network and browser

- Use valid HTTPS for UI, API, and every MCP hostname; retain TLS verification on all outbound connections.
- Keep remote source/private-host allowlists empty by default and review DNS/redirect behavior for every exception.
- Retain CSP, frame denial, content-type protection, permissions policy, referrer policy, exact frontend origin, secure cookies, and CSRF enforcement.
- Terminate request bodies and timeouts at both proxy and application bounds. Monitor repeated auth, validation, oversized-body, and denied-host events.

## Data, builds, and releases

- Apply migrations as an explicit controlled step; never let multiple application replicas race schema changes.
- Require source provenance, deterministic mappings, exact coverage, no blocking findings, artifact hashes, compatible runtime version, and configured inbound auth before deployment.
- Promote only digest-pinned release images after CI, secret/dependency/source/container scans, SBOM/checksum generation, and signature verification.
- Encrypt backups, separate key escrow from data, restrict restore access, and complete a documented restore drill.

Record evidence for every item in the release checklist. Any unverified item is an open production gate, not an implied pass.
