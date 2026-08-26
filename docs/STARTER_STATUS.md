# MCPlica Pre-stable Release Status

The repository has moved beyond its original starter scaffold. It now carries frozen Python/pnpm locks, typed builder/runtime contracts, control-plane authentication and project workflows, source/build/deployment evidence, the generic MCP runtime, a responsive ten-step UI, behavior/E2E tests, hardened containers, CI/security/release automation, and user/operator/security/governance documentation.

This file is retained for links from the initial repository history. Current implementation authority remains the six documents in `docs/`, while production promotion is governed by `docs/release/release-checklist.md` and `AGENT3_HANDOFF.md`.

## Not a production certification

Repository-controlled work does not prove hosted settings or an operator environment. Before the first production release, the project must still configure and prove branch protection/required checks, the founder-approved CLA service and final legal text, private vulnerability reporting, a tagged GHCR release/signature, live DNS/TLS, production secrets and network policy, an isolated restore drill, and end-to-end runtime operation against the target host.

## CLA gate

`.github/workflows/cla.yml` intentionally fails closed until the GitHub organization-approved CLA verification service is configured. This prevents unverified external contributions from being merged.
