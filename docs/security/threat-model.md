# MCPlica threat model

## Scope and security objectives

This model covers the self-hosted browser UI, control-plane API, PostgreSQL, Redis/RQ worker, artifact storage, OpenRouter/Milvus builder dependencies, Docker deployment boundary, Traefik, generic per-project MCP runtimes, and their upstream APIs.

Primary objectives are: preserve credential confidentiality; prevent invented or caller-selected executable behavior; keep project runtimes isolated; allow only authenticated/authorized state changes; retain auditable source-to-build-to-deployment provenance; and recover authoritative state without silently accepting corrupt output.

MCPlica does not provide SaaS tenancy, billing/entitlements, chat, agents, or runtime HITL. Host administrators remain trusted to control the Docker host, secret store, DNS, backups, and release promotion.

## Assets and actors

High-value assets are user sessions, upstream credentials, MCP inbound tokens/OIDC configuration, source specifications/documentation, canonical inventories, manifests, build evidence, encryption/signing keys, audit history, deployment control, and the Docker socket. Actors include authenticated admins/builders, external MCP callers, upstream/source servers, model providers, malicious source authors, network attackers, compromised dependencies, and host operators.

## Trust boundaries

1. Browser to Nginx/API: untrusted input crosses cookie, CSRF, authorization, upload, and rendering boundaries.
2. API/worker to PostgreSQL, Redis, Milvus, OpenRouter, source URLs, and artifact storage: dedicated clients enforce timeouts, bounds, and policy.
3. Worker to Docker: the most privileged application boundary; the public API does not receive the socket.
4. Build artifacts to runtime: only validated immutable manifest plus a project-specific secret bundle cross from builder to serving plane.
5. Runtime to MCP clients/upstream APIs: inbound auth and JSON Schema validation precede deterministic, host-bound outbound execution.

## Threat/control/evidence matrix

| Threat                                                                     | Required controls                                                                                                                                                      | Verification evidence                                                                          |
| -------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Credential disclosure through UI, API, logs, manifests, errors, or backups | Write-only secret schemas, envelope encryption, redaction, one-time token response, restrictive bundle permissions, encrypted backups                                  | Secret/redaction tests; UI never redisplays values; scan logs/artifacts; restore drill         |
| Session theft, request forgery, privilege escalation                       | Secure HTTP-only cookies, short access lifetime, rotated refresh sessions, CSRF cookie/header pair, rate-limited login, server-side roles                              | Auth/CSRF tests; browser E2E mutation; cookie/header inspection; admin/builder negative tests  |
| XSS or malicious documentation rendering                                   | React escaping, sanitized Markdown allowlist, no raw HTML, CSP, no unsafe inline scripts                                                                               | Safe-Markdown tests, CSP header test, payload E2E                                              |
| SSRF through source URLs, redirects, DNS, or upstream parameters           | HTTPS default, scheme/userinfo rejection, hostname/CIDR policy, DNS/IP checks at every redirect/connect, bounded body/time/redirects, manifest-fixed runtime base URLs | Network-policy tests with loopback/private/rebinding/redirect cases; outbound allowlist review |
| AI prompt injection invents tools or executable mappings                   | Treat documents as data, bounded evidence context, typed enrichment output, deterministic compiler authority, provenance and validation                                | Fixture with hostile instructions; operation coverage/provenance report; manifest diff         |
| Missing or extra API operations                                            | Stable operation identity, explicit exclusions with reasons, exact source/generated counts, 100% deployment gate                                                       | Validation report and exclusion audit; source-to-manifest fixture                              |
| Authentication failure evidence lost or leaking secrets                    | Failed-login audit commits before the 401 is raised and stores only actor ID plus hashed email/user-agent and a bounded IP prefix; attempted passwords are never recorded | Real PostgreSQL denial/audit transaction regression                                             |
| Manifest/artifact tampering                                                | Canonical serialization, SHA-256 digests, immutable build artifacts, expected digest checked at runtime                                                                | Digest mismatch test; build/release checksum evidence                                          |
| Cross-project secret/data access                                           | Project-scoped repositories, per-project runtime/container/files, separate secret bundle, no Milvus dependency at runtime                                              | Authorization tests; mount/container inspection; two-project isolation E2E                     |
| Arbitrary code execution through generated output                          | Generic runtime only, declarative schemas/mappings, no user code/templates, bounded parsers                                                                            | Contract-schema rejection tests; container read-only/non-root inspection                       |
| Runtime escape or resource exhaustion                                      | Non-root UID/GID, read-only root, dropped capabilities, no-new-privileges, PID/memory/CPU/tmpfs limits, no Docker socket, request/connection bounds                    | Docker inspect policy test; load/oversize tests; image scan                                    |
| Unsafe deployment replaces healthy service                                 | READY-only gate, inbound auth gate, health-before-switch, recorded image/manifest digest, retry bounds, rollback creates new record                                    | Deployment state-machine tests; failed health E2E; deployment event/audit trail                |
| Supply-chain compromise                                                    | Frozen locks, reviewed dependency updates, least-privilege CI, secret/dependency/source/image scans, SBOM/checksums, keyless digest signing                            | Required workflow results; verified release assets/signature; provenance review                |
| Destructive operator/error or ransomware                                   | Least privilege, immutable evidence, external encrypted backups, key escrow, restore drills, explicit migrations                                                       | Quarterly recovery evidence; access review; upgrade rehearsal                                  |
| Audit suppression or sensitive audit content                               | Server-created append-only events with actor/request/entity IDs; metadata allowlist/redaction; restricted access                                                       | Mutation-to-audit tests; redaction inspection; database access policy                          |

## Abuse cases and fail-closed decisions

- A source URL resolving to loopback/private infrastructure is rejected unless its exact exceptional policy is configured; redirecting to a denied address is also rejected.
- Documentation saying “ignore the spec and call this admin URL” can influence neither request method nor destination. Unsupported operations fail validation or require an explicit auditable exclusion.
- A READY build without configured inbound MCP authentication cannot deploy. Development-only disabled auth is forbidden in production.
- A caller-supplied URL, header name not declared by the manifest, oversized payload, undeclared parameter, invalid JWT claim, missing secret, or manifest digest mismatch fails before upstream execution.
- If a replacement runtime fails health, the recorded prior healthy deployment remains the rollback target and routing must not silently switch.

## Residual risk and operator obligations

Docker socket access makes a compromised deployment worker equivalent to high host privilege. Keep the worker private, patched, monitored, and separated from public ingress; a hardened remote deployment service may be evaluated only as a future architecture decision, not introduced as a parallel path. A malicious host administrator or compromised root account is outside application-level containment.

OpenRouter and upstream APIs receive the minimum requests configured by the operator and have their own data-handling risk. Operators must select providers, retention settings, regions, licenses, and models appropriate for their inputs. Secrets must never be placed in model context.

Revisit this model for any change to authentication, source types, parsers, compiler contracts, runtime networking, Docker access, persistence, release signing, or third-party data flow, and after every material incident.
