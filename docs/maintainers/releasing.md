# Releasing MCPlica

MCPlica releases are immutable source tags plus three container images (`backend`, `frontend`,
and `runtime`), source and image SBOMs, checksums, keyless signatures, and provenance
attestations. A successful repository workflow does not certify an operator environment.

## Version and branch conventions

Root `VERSION` is authoritative and contains SemVer without a leading `v`, for example `1.0.0` or
`1.0.0-rc.1`. Release branches use `release/vX.Y.Z-preparation`; annotated tags and GitHub Releases
use matching `vX.Y.Z` names. Published tags and container tags are never moved, reused, or
overwritten.

User, operator, security, and compatibility changes enter `CHANGELOG.md` under `[Unreleased]`.
Release preparation moves them to a dated version section and creates matching notes under
`docs/releases/`.

## Prepare and review a candidate

1. Branch from current `master` and confirm no private, generated, ignored, or unrelated files are
   included.
2. Update `VERSION`, the changelog, and release notes, then run
   `python scripts/release_version.py --sync`.
3. Regenerate the contract-matrix goldens, contract schemas, OpenAPI output, and frontend API
   bindings when required. Then stage the intended tree, run the checksum command, and stage the
   manifest: `python scripts/checksum_manifest.py --write`.
4. Run the repository, API contract, lint, type, test, migration, browser, Compose, dependency,
   secret, and candidate-image gates.
5. Open a pull request and require all checks on its exact head. Obtain an independent approval
   when an eligible independent maintainer exists. While the project has only one maintainer, an
   owner-authorized self-merge must be recorded explicitly and must not be presented as independent
   review; an unavailable or failed automated control is never waived.
6. Merge, wait for default-branch security indexing, and verify the accepted commit is contained in
   the exact `master` head.

The acceptance harness is destructive to its disposable installation. Never run it against
retained development or production data.

## Publish after acceptance

From a clean checkout of the accepted `master` commit:

```bash
git switch master
git pull --ff-only origin master
python scripts/release_version.py --check
python scripts/checksum_manifest.py --check
git status --short
git tag -s -a v1.0.0-rc.1 -m "MCPlica v1.0.0-rc.1"
git push origin v1.0.0-rc.1
```

Use the value in `VERSION`; the prerelease above is the current example. If no approved signed-tag
identity exists, use an annotated tag without `-s`. Lightweight tags are rejected. The tag-only
release workflow verifies version equality, `master` ancestry, exact-commit checks, image scans,
SBOMs, checksums, signatures, attestations, and immutable publication boundaries.

No workflow creates `latest`, floating major or minor tags, production deployment, or a second
release path.

## Failure and withdrawal

A partially failed publication may leave immutable image tags without a GitHub Release. Do not
overwrite them or move the source tag. Investigate and publish a new patch or prerelease. For a
defective completed release, document impact and direct operators to a verified previous digest
or coordinated recovery point.

Application rollback is safe only when the older code supports the current schema. Otherwise,
restore the coordinated database, artifact, runtime-root, and key backup.
