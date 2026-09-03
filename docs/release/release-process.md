# Release process

MCPlica releases are immutable source tags plus three container images (`backend`, `frontend`,
and `runtime`), source/image SBOMs, checksums, keyless signatures, and provenance/SBOM
attestations. A successful repository workflow does not certify an operator environment; complete
the target-host gates in the release checklist separately.

## Version, branch, and changelog conventions

Root `VERSION` is authoritative and contains SemVer without `v` or build metadata, such as `1.2.3`
or `1.2.3-rc.1`. Release branches use `release/vX.Y.Z-preparation`; annotated tags and GitHub
Releases use the matching `vX.Y.Z`. Published source tags and container tags are never moved,
deleted for reuse, or overwritten. A correction uses a new patch/prerelease version.

Normal branches use `feature/`, `fix/`, or `docs/`. User/operator/security/compatibility changes
enter `CHANGELOG.md` under `[Unreleased]`. Release preparation moves them to a dated version section
and creates `docs/releases/vX.Y.Z.md`. Do not rely on generated GitHub notes as the release contract.

## Prepare one reusable release candidate

1. Branch from current `master`; confirm no unrelated or secret files are present.
2. Edit `VERSION`, run `python scripts/release_version.py --sync`, regenerate OpenAPI/frontend
   contracts, and update changelog/release notes. Review internal schema/prompt identifiers
   separately; they are not blindly coupled to the product version.
3. Reconcile the six authoritative design documents, migrations, lockfiles, Dockerfiles/Compose,
   compatibility matrix, operator/security docs, and generated artifacts. Stage the intended tree,
   run `python scripts/checksum_manifest.py --write`, and stage `MANIFEST.sha256`; the manifest
   hashes canonical Git index blobs so Windows/Linux checkout line endings cannot change it.
4. Run `make repository-check`, `make api-contract-check`, formatting, lint, type checks, component
   tests, critical coverage, migration round trips/drift, frontend build/browser tests, and the
   complete disposable Compose acceptance workflow.
5. Build all three images through canonical Compose, check OCI version/source/revision/license and
   non-root user metadata, and scan each candidate for unaccepted HIGH/CRITICAL findings.
6. Update `docs/evidence/vX.Y.Z-release-candidate.md` with exact commands/results and clearly list
   hosted/production checks not performed. Commit, push, and open the release-readiness pull request.
7. Require normal review plus successful CI, Security, CLA (where applicable), and repository-rule
   checks on the exact PR head. Merge without bypassing failed or unavailable required checks.

The acceptance harness is destructive to its disposable installation. It must never run during
ordinary deployment startup or against retained development/production data.

## Hosted repository prerequisites

Before publication, verify `master` rules require pull requests, CODEOWNERS review for sensitive
paths, conversation resolution, current CI/Security/CLA checks, force-push/deletion prevention, and
administrator enforcement. Restrict Actions to the recursively audited direct and composite-action
closure at full commit SHAs, keep the default workflow token read-only, and prevent workflows from
approving pull requests. Enable Dependabot vulnerability alerts and automated security fixes, then
resolve or explicitly disposition every open alert. Confirm Actions may issue OIDC tokens, write
GHCR packages/attestations, and create releases; enable and test GitHub private vulnerability
reporting, code scanning, and secret scanning; configure the founder-approved CLA service/context.
These settings cannot be proven by committed files alone, so retain exact API/settings and hosted
run evidence for the reviewed release commit.

The repository-managed label catalog is `.github/labels.json`; its workflow updates catalogued
labels on `master` without deleting extra project labels.

## Publish after acceptance

From a clean checkout after the release-readiness pull request is merged:

```bash
git switch master
git pull --ff-only origin master
python scripts/release_version.py --check
git status --short
git tag -s -a v1.0.0 -m "MCPlica v1.0.0"
git push origin v1.0.0
```

Use the version read from `VERSION`; `v1.0.0` above is the current example. If the project has no
approved signed-tag identity, create an annotated tag with `git tag -a`; lightweight tags are
rejected. Do not push a tag until successful CI and Security **push** runs exist for that exact
`master` SHA.

The tag is the only publication trigger. `.github/workflows/release.yml` then:

1. verifies exact tag/VERSION equality, changelog/notes, annotated tag type, `master` ancestry, and
   successful CI/Security runs for the tagged SHA;
2. refuses an existing GitHub Release or container tag;
3. builds each repository Dockerfile with exact version, source SHA, and source URL OCI metadata;
4. scans before push, creates an SPDX JSON SBOM, pushes the version tag, resolves the digest, signs
   and immediately verifies that digest;
5. attaches build provenance and the SBOM to the immutable registry digest;
6. creates a source archive/source SBOM, per-image evidence/checksums, overall `SHA256SUMS`, and a
   keyless signature bundle; and
7. passes the committed notes and every asset to one `gh release create` operation so GitHub CLI
   stages the draft, uploads the assets, and publishes only after the asset upload succeeds.

No workflow creates `latest`, floating major/minor tags, production deployment, or a second release
path.

## Consumer verification

Download every release asset and verify its filenames against the release page before execution:

```bash
sha256sum --check SHA256SUMS
cosign verify-blob \
  --bundle SHA256SUMS.bundle.json \
  --certificate-identity "https://github.com/waqoor/MCPlica/.github/workflows/release.yml@refs/tags/v1.0.0" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  SHA256SUMS
```

Read each `*.release.txt`, retain its exact `image@sha256:digest`, and verify image signature and
attestations against the same tag-specific workflow identity:

```bash
cosign verify \
  --certificate-identity "https://github.com/waqoor/MCPlica/.github/workflows/release.yml@refs/tags/v1.0.0" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  ghcr.io/waqoor/mcplica/runtime@sha256:<digest>

cosign verify-attestation --type slsaprovenance \
  --certificate-identity "https://github.com/waqoor/MCPlica/.github/workflows/release.yml@refs/tags/v1.0.0" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  ghcr.io/waqoor/mcplica/runtime@sha256:<digest>
```

Repeat for backend/frontend and review each SPDX SBOM plus scanner result. Configure production
Compose with digest references only; never translate them back to mutable tags.

## Failure, withdrawal, and rollback

A partially failed publication may leave one or more immutable image tags without a GitHub
Release. Do not overwrite them or rerun by moving the tag. Investigate, record the partial state,
and publish a corrected patch/prerelease version. For a defective completed release, document
impact, withdraw it without destroying evidence as appropriate, and direct operators to a tested
previous digest or coordinated recovery point.

Application rollback is allowed only when the older code supports the current schema. Otherwise
restore the pre-upgrade database/artifact/runtime-root/key set. Project runtime rollback remains the
normal immutable-Build lifecycle. Security embargoes use a private advisory and coordinated patch.
