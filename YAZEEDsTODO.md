# Current organization and public-prerelease handoff

Live audit date: 2026-09-04.

## Completed repository work

- The canonical repository is now the `waqoor/MCPlica` organization repository.
- Founder/owner approval of exact commit
  `22ee7926f7117f26c0d8ca8f6cfa123d3a62c5bd` is recorded in
  [PR #44](https://github.com/waqoor/MCPlica/pull/44#issuecomment-5532626474). It is explicitly
  founder/release authorization, not an independent technical review.
- PR #44 was merged to `master` as
  `6d09e4c431acc37174342e7bdd608aed58332362`.
- The post-transfer integration branch contains the exact PR #46 Nginx update and exact PR #47
  source-configuration/QA head, plus organization namespace, immutable-release, documentation,
  and regression-test corrections.
- All public repository, Docker source, GHCR, issue-template, signature-identity, and evidence links
  now use `waqoor/MCPlica`; founder profile and CODEOWNERS references remain `@yazeedhasan97`.
- The complete owner-operated GitHub control list is
  [docs/release/github-public-prerelease-settings.md](docs/release/github-public-prerelease-settings.md).

## Remote branch disposition

| Branch | Disposition |
|---|---|
| `docs/final-release-evidence` | Already contained in `master`; do not remerge. |
| `fix/cleanup-cycle-retry` | Already contained in `master`; do not remerge. |
| `fix/compose-e2e-validation-20260901` | Already contained in `master`; do not remerge. |
| `fix/final-release-closure-20260903` | Approved exact head is contained in `master` through PR #44. |
| `fix/post-merge-compose-hardening-20260901` | Already contained in `master`; do not remerge. |
| `release/v1.0.0-preparation` | Already contained in `master`; do not remerge. |
| `dependabot/docker/infra/docker/nginxinc/nginx-unprivileged-1.31.5-alpine3.24-slim` | Exact head incorporated once into the integration branch. |
| `qa/mohammed-ghunaim` | Exact head incorporated once into the integration branch; nested domain-to-response validation now has a regression test. |
| `fix/foundation-closure-20260901` | Intentionally not merged: its only unique file is an obsolete temporary PostgreSQL-binary review workflow. |

No remote branch was deleted.

## Publication boundary

The checkout remains synchronized to `1.0.0`, which looks final. Before publishing, choose and
synchronize a prerelease such as `1.0.0-rc.1` / `v1.0.0-rc.1`; add matching changelog/release
notes and rerun every exact-head gate. Do not publish `v1.0.0` as the requested prerelease.

The integration pull request is the source of truth for its exact final SHA and hosted CI,
Security, CLA, dependency, secret, image, and Compose results. It must not merge on a failing or
pending gate.

## Owner actions still required

1. Make the repository public only after the staged/public snapshot and full Git history are clean.
2. Add a second trusted organization owner and require secure 2FA after checking collaborator and
   service-account readiness.
3. Configure the active `master` and `v*` rulesets, exact required checks, independent review,
   force-push/deletion blocks, and narrowly controlled bypass described in the owner checklist.
4. Enable and verify private vulnerability reporting, CodeQL for Python and JavaScript/TypeScript,
   secret scanning, repository push protection, security notifications, and immutable releases.
5. Confirm Dependabot alert #1 closes as fixed after default-branch re-indexing; do not dismiss it.
6. Appoint an independent maintainer/reviewer and update CODEOWNERS/team scope. Repository write
   access alone is not a governance appointment.
7. Configure and test the founder-approved external CLA service/context before accepting an
   untrusted contribution.
8. Select the prerelease version, obtain independent review of its exact final head, create the
   annotated/signed tag, and verify every Release/GHCR checksum, signature, SBOM, digest, and
   attestation.
9. Keep production DNS/TLS, target-host, real-provider, backup/restore, upgrade, rollback, and
   recovery gates open until separately executed. A public prerelease is not production
   certification.
