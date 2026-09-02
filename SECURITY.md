# Security Policy

## Supported versions

| Version | Support status |
| --- | --- |
| `1.0.x` | Supported after `v1.0.0` publication; fixes land on `master` and the latest compatible release line |
| Release-candidate commits | Evaluation only; do not expose to untrusted networks without the full operator review |
| `<1.0.0` snapshots | Unsupported; upgrade using the v1.0.0 migration guidance |

Support status does not certify an individual deployment. Operators must verify target-host
hardening, TLS, secrets, image signatures/digests, monitoring, and recovery.

## Private reporting

Do not disclose an exploitable vulnerability in an issue, discussion, pull request, log excerpt, or public test fixture. Use [GitHub private vulnerability reporting](https://github.com/yazeedhasan97/MCPlica/security/advisories/new). Include the affected commit/version, component, impact, minimal reproduction, and any suggested mitigation. Remove credentials, proprietary API material, and personal data.

The maintainer will acknowledge a usable report, validate severity, coordinate a fix and release, and agree on disclosure timing. Response times depend on maintainer availability and are goals rather than a paid SLA. Good-faith researchers who respect privacy, avoid persistence/data destruction, and allow coordinated remediation will be credited if they wish.

## Security invariants

- Browser authentication uses secure HTTP-only session cookies plus CSRF validation for state changes; authorization is enforced by the API, never by hidden UI controls alone.
- Stored credentials are encrypted and write-only through the UI/API. Plaintext secrets must not enter logs, manifests, audit metadata, events, or build evidence.
- Remote source retrieval and runtime upstream execution use bounded requests, TLS verification, DNS/IP checks, and explicit host policy. MCP callers cannot supply arbitrary destinations.
- Executable mappings derive from source evidence. AI enrichment cannot create unaudited HTTP behavior and never runs in an MCP serving runtime.
- Each project runtime is manifest-driven, isolated, non-root, resource-bounded, read-only where practical, and receives only its own mounted secret bundle. The public API container does not receive the Docker socket.
- Production control-plane configuration fails closed without dedicated encryption/signing/pepper keys, TLS routing, an immutable runtime image digest, and an absolute runtime artifact root.
- Release workflows scan source, dependencies, and images; publish SBOMs and checksums; and keylessly sign immutable image digests.

The detailed abuse cases, trust boundaries, control owners, and verification evidence are in `docs/security/threat-model.md`. Deployment hardening and incident procedures are in `docs/operations/`.
