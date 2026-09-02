# Release process

MCPlica releases are immutable source tags plus three signed container images (`backend`, `frontend`, and `runtime`), SBOMs, digest evidence, and checksums. A tag does not make an installation production-ready; the operator gates in `release-checklist.md` still apply.

## Repository controls

Before the first external contribution or release, enable private vulnerability reporting, configure the founder-approved CLA service, and protect `master`: require pull requests, CODEOWNERS review for sensitive paths, conversation resolution, successful CI/security/CLA checks, signed or otherwise attributable commits per project policy, blocked force pushes/deletion, and administrator enforcement. These are GitHub-hosted settings and cannot be truthfully completed by repository files alone.

## Prepare

1. Reconcile the release against the six authoritative documents and update version/changelog/release notes.
2. Confirm frozen Python/pnpm locks, migrations, contracts, generated schemas/artifacts,
   documentation, and `MANIFEST.sha256` are synchronized. For the 2026-09-02 schema line, rehearse
   migrations `0021` through `0025` and the documented source-selection downgrade refusal.
3. Run lint, format checks, type checks, unit/integration tests, frontend production build, cross-browser E2E, Compose rendering, image builds, non-root/health/header checks, and secret/dependency/source/image scans.
4. Complete threat-model review, upgrade/rollback rehearsal, backup/restore drill, and live TLS/MCP authentication acceptance for the target environment.
5. Resolve every blocker or mark the release not ready. Do not waive deterministic coverage, secret, auth, network, image-digest, or runtime-health gates.

Create an annotated SemVer tag on a commit already merged to `master`, for example `v1.0.0` or `v1.0.0-rc.1`. The release workflow verifies SemVer, default-branch ancestry, and a successful CI run for that exact SHA.

## Automated publication

For each component, `.github/workflows/release.yml` builds the repository Dockerfile, scans HIGH/CRITICAL image findings, creates an SPDX JSON SBOM, pushes the tagged GHCR image, resolves its immutable digest, and signs that digest keylessly with GitHub Actions OIDC. It publishes image/digest/source evidence and SHA-256 checksum files to the GitHub release. A failed matrix component prevents the release job.

## Consumer verification

Download release assets and verify checksums:

```bash
sha256sum --check backend.sha256
sha256sum --check frontend.sha256
sha256sum --check runtime.sha256
```

Read each `*.release.txt`, pull the recorded digest, and verify its signature using the tag-specific workflow identity:

```bash
cosign verify \
  --certificate-identity "https://github.com/yazeedhasan97/MCPlica/.github/workflows/release.yml@refs/tags/v1.0.0" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  ghcr.io/yazeedhasan97/mcplica/runtime@sha256:<digest>
```

Review the SBOM and scanner results for accepted residual risk. Set Compose image variables to the verified digest references; never translate them back to mutable tags.

## Rollback and withdrawal

Do not move or reuse a published tag. For a defective release, document impact, mark/withdraw assets as appropriate, publish a patched version, and direct operators to tested previous digests or the recovery procedure. A security embargo uses a private advisory and coordinated release. Preserve build/SBOM/signature evidence even when a release is withdrawn.
