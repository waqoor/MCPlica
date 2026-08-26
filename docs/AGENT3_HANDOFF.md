# Agent 3 handoff

**Status:** the repository-owned frontend, UX, operational-hardening, governance, and release-readiness scope is complete in the shared checkout as of 2026-08-26. This is not a production-environment certification; the promotion gates below remain deliberately open.

## Delivered

- Complete responsive ten-step workspace with durable routes, accessible loading/error/empty states, role-aware actions, validation/evidence views, and source-to-runtime lifecycle UX.
- Typed API/domain clients with normalization at the client boundary, TanStack Query orchestration, abortable cached reads, lazy routes, bounded polling/SSE, pagination, and no raw component-side external calls.
- Canonical project-scoped deployment UX. The global Deployments screen is a project navigator because no global deployment collection exists in the backend contract.
- Cross-browser behavior/security E2E, focused unit tests, local fonts, sanitized Markdown, CSP-compatible output, and hardened security headers.
- Pinned CI, security, dependency-review, SBOM, image-scan, GHCR, checksum, and keyless Cosign release workflows; frozen dependency locks and Dependabot coverage.
- Non-root/read-only container and Compose hardening, fail-closed production TLS/domain/image configuration, secret generation, and operator/security/release/governance documentation.

Full requirement mapping is in `docs/evidence/agent3-requirement-traceability.md`; production sign-off is controlled by `docs/release/release-checklist.md`.

## Final local evidence

| Gate                          | Result                                                                                                                                                                                             |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Frontend static/unit/build    | Prettier, ESLint, TypeScript, 4 Vitest files/7 tests, and production Vite build passed                                                                                                             |
| Browser behavior              | 12 passed, 4 intentional project-specific skips across Chromium, Firefox, WebKit, and mobile Chromium                                                                                              |
| Live API contract             | 49 OpenAPI paths reconciled with `docs/api-inventory-v1.md`; production-placeholder/raw-component-call sweeps clean                                                                                |
| Backend/contracts integration | Ruff and format clean; strict Pyright 0 errors; 54 passed, 1 environment-gated skip                                                                                                                |
| Runtime integration           | Ruff and format clean; strict Pyright 0 errors; 22 passed                                                                                                                                          |
| Dependencies and source       | pnpm and locked-Python audits found no known vulnerabilities; Trivy 0.74 source vulnerability/misconfiguration/secret scan found no HIGH/CRITICAL blocker                                          |
| Images                        | Backend/runtime/frontend build; non-root users `10001:10001`, `10001:10001`, `101:101`; all three Trivy HIGH/CRITICAL scans clean                                                                  |
| Runtime/container smoke       | Backend import passed; runtime development config passed and production omitted-digest case failed closed; frontend read-only/cap-drop/no-new-privileges health/homepage/seven-header smoke passed |
| Configuration                 | Base and production Compose render passed; starter validator checked 32 required files; generated encryption key decoded to 32 bytes                                                               |

Test mocks remain confined to tests. No chat, Agents, HITL, SaaS tenancy, billing, sponsorship entitlement, alternate persistence/runtime, V2, canary, shadow, or compatibility path was introduced.

## Promotion gates

- Configure and require hosted branch protection, CI/security/CLA/CODEOWNERS review, private vulnerability reporting, and the founder-approved individual/entity CLA text and verification service.
- Activate the founder's verified funding channel and update `.github/FUNDING.yml` before claiming the documented launch sponsorship pathway.
- Run the first hosted CI/security/tag workflow and retain the exact GHCR digests, SBOMs, checksums, and verified Cosign signatures.
- Provision real DNS/ACME/TLS, immutable images, unique secrets, least-privilege data/network/host permissions, monitoring and incident contacts; then prove unknown-host denial, secure cookies/headers, and authenticated `/mcp` on the target host.
- Complete an encrypted backup and isolated restore drill, upgrade/project-rollback rehearsal, and record RPO/RTO evidence.
- Because Agents 1 and 2 worked concurrently in the same checkout, rerun the required hosted checks on the final integrated commit; do not promote a partial working-tree snapshot.
