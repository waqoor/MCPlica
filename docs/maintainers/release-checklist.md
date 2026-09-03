# Release checklist

Every checked item needs an exact URL, workflow run, command output, or protected release record
for the candidate commit. An unknown item remains unchecked. Local results cannot satisfy a hosted
repository or production-host gate.

## Candidate identity

- [ ] `VERSION`, package metadata, locks, API output, runtime metadata, changelog, and release notes
      agree; `python scripts/release_version.py --check` passes.
- [ ] Generated files and `MANIFEST.sha256` match the fully staged Git index.
- [ ] The complete Git history and hosted collaboration surface are free of live credentials and
      private customer, employee, source, fixture, issue, artifact, or screenshot data.
- [ ] No tracked `.env`, runtime secret bundle, disposable output, review scratch file, or merge
      marker is present.

## Repository controls

- [ ] `master` and release-tag rules require pull requests where applicable, independent review,
      conversation resolution, exact CI and security checks, and block force pushes and deletion.
- [ ] Actions are limited to the reviewed, immutable action closure; workflow tokens are read-only
      by default and cannot approve pull requests.
- [ ] Dependabot, private vulnerability reporting, code scanning, secret scanning, push protection,
      and a private security-reporting route are enabled and tested.
- [ ] Maintainer, collaborator, OIDC, registry, release, and organization recovery access is
      reviewed; at least two trusted organization owners use strong 2FA.
- [ ] The approved CLA service is tested on a real external-contributor pull request.

## Product and supply chain

- [ ] Frozen installs, formatting, linting, strict type checks, backend/runtime/contract tests,
      critical coverage, frontend unit/build/browser tests, and migration rehearsals pass.
- [ ] Canonical Compose render, build, startup, live browser, authenticated MCP, lifecycle,
      rollback, outage recovery, and persistence checks pass on a disposable supported host.
- [ ] Dependency, secret, source, configuration, and all candidate-image scans have no unaccepted
      blocker.
- [ ] Release images carry correct version, source, revision, license, and non-root metadata.

## Publication and operations

- [ ] The annotated `v<VERSION>` tag points to the independently reviewed `master` commit, and no
      matching Release or registry tag already exists.
- [ ] Source and image SBOMs, checksums, signatures, immutable digests, and provenance attestations
      are published and independently verified.
- [ ] Production host hardening, DNS/TLS, provider access, monitoring, encrypted backup and isolated
      restore, upgrade, rollback, and recovery tests are complete before production promotion.

Follow [the release process](releasing.md) and the version-specific notes under `docs/releases/`.
