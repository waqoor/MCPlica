# GitHub public-prerelease owner checklist

This is the owner-operated control ledger for moving `waqoor/MCPlica` from a private GitHub Free
organization repository to a public prerelease. Repository code cannot enable or prove these
GitHub settings. Keep screenshots or API output and the final workflow URLs with the release
evidence.

Last live audit: 2026-09-04, before the public-visibility change.

## Current live state

| Control | Observed state | Required disposition |
|---|---|---|
| Repository identity | Organization repository `waqoor/MCPlica`; private; default branch `master` | Make public only after the pre-public checks below pass. |
| Organization ownership | `@yazeedhasan97` is the sole organization owner | Appoint a second trusted owner for continuity. |
| Organization 2FA policy | Not required by the organization | Require 2FA and secure 2FA methods after checking every member, outside collaborator, bot, and recovery path. |
| Repository collaborators | `@yazeedhasan97` admin; `@mohd-ghnm-X` direct write | Confirm the direct write grant is still required; prefer a least-privilege team. |
| Actions | Enabled; selected actions only; all allowed action references are pinned to full SHAs; default token is read-only and cannot approve pull requests | Preserve this policy and recheck it after transfer/publication. |
| Branch protection / rulesets | Not active; the GitHub API reports that the current private repository needs a paid plan or public visibility | Configure the `master` and release-tag rulesets immediately after the repository becomes public. |
| Dependabot alerts / fixes | Alerts and automated security fixes enabled; alert #1 was open at audit start while the patched dependency was not yet indexed on `master` | Confirm GitHub closes it as fixed after default-branch re-indexing; do not dismiss it. |
| Private vulnerability reporting | Disabled/unavailable while private on the current plan | Enable immediately after public visibility and test the external report path. |
| Code scanning | CodeQL default setup unavailable while private on the current plan | Enable default setup for Python and JavaScript/TypeScript after public visibility. |
| Secret scanning | Repository secret scanning disabled while private on the current plan | Confirm automatic public scanning, enable repository push protection, and triage the full-history scan. |
| Immutable releases | Disabled | Enable before creating the first GitHub Release; it applies only to future releases. |
| Repository environments, Actions secrets/variables, deploy keys, and webhooks | None found | This is acceptable for the current tag-driven release, but verify GHCR and OIDC permissions on the real prerelease run. |

## 1. Before changing visibility

- [ ] Merge only reviewed, applicable branch work. Retain the branch-disposition record; do not
      merge obsolete review scaffolding merely because it is unmerged.
- [ ] Select a SemVer prerelease identity. `1.0.0-rc.1` / `v1.0.0-rc.1` is the recommended first
      public candidate; do not publish the final `v1.0.0` tag for a prerelease. Update `VERSION`,
      run `python scripts/release_version.py --sync`, add the matching dated changelog section and
      `docs/releases/v1.0.0-rc.1.md`, regenerate contracts/artifacts, and rerun all gates.
- [ ] Scan the complete Git history and every remote branch for credentials and private customer,
      employee, source-specification, test-fixture, issue, or artifact data. Revoke/rotate a real
      credential before removing it from history; deletion alone does not make it safe.
- [ ] Review all public-facing Issues, pull requests, comments, Actions logs/artifacts, release
      evidence, contributor identities, screenshots, and documentation. Public visibility exposes
      more than the default-branch checkout.
- [ ] Confirm AGPL-3.0-only, trademark, CLA, contribution, security, support, governance, and
      generated-output policies are the intended public terms. Configure the approved external CLA
      service and `CLA_STATUS_CONTEXT` before accepting an untrusted contribution.
- [ ] Confirm the organization owns or can publish `ghcr.io/waqoor/mcplica/{backend,frontend,runtime}`
      and that packages inherit the intended visibility and repository access. Do not assume package
      permissions changed correctly with the repository transfer.
- [ ] Run the exact integration head through CI, Security, and CLA. Obtain an independent technical
      review of that exact head. Founder approval is release authorization, not a substitute for
      independent review.

## 2. Organization controls

Configure these under organization **Settings** before inviting more contributors:

- [ ] **Ownership continuity:** promote one independently controlled, trusted member to
      organization owner. Both owners should have passkeys or hardware security keys and tested
      recovery methods. Do not use a shared account.
- [ ] **Authentication security:** first verify 2FA readiness for members, outside collaborators,
      and service accounts; then enable **Require two-factor authentication for everyone** and
      **Only allow secure two-factor methods**. GitHub can remove non-compliant outside
      collaborators, so coordinate this change rather than enabling it blindly.
- [ ] **Base permissions:** retain `Read` as the default repository permission. Grant write,
      maintain, admin, security-manager, and billing roles only where required.
- [ ] **Member privileges:** restrict repository creation, deletion, transfer, visibility changes,
      outside-collaborator invitations, integration installation, and Pages publication to owners
      or explicitly trusted roles. The live audit found these privileges broadly enabled.
- [ ] **Teams:** create visible `maintainers` and `security` teams with the smallest useful
      permissions. Appoint real members before changing `CODEOWNERS`; a team name alone provides no
      independent review.
- [ ] **Outside collaborators:** review `@mohd-ghnm-X`, `@Q-Hamza`, and `@raghadkhudair` across the
      organization. Keep only required repository grants and convert ongoing collaborators to
      appropriately scoped teams when membership is intended.
- [ ] **Apps and OAuth:** review installed GitHub Apps after the transfer. Install the Codex GitHub
      App on `waqoor/MCPlica` only if repository access through that connector is desired; the audit
      could access the former personal installation but not the organization repository.
- [ ] **Audit and notifications:** make both owners/security maintainers watch security alerts and
      review the organization audit log after every control change.

GitHub recommends at least two organization owners and documents the access impact of enforcing
secure 2FA:

- <https://docs.github.com/en/organizations/managing-peoples-access-to-your-organization-with-roles/maintaining-ownership-continuity-for-your-organization>
- <https://docs.github.com/en/organizations/keeping-your-organization-secure/managing-two-factor-authentication-for-your-organization/requiring-two-factor-authentication-in-your-organization>

## 3. `master` branch ruleset

After making the repository public, create one repository ruleset under **Settings > Rules >
Rulesets**. Use it as the single source of truth instead of layering a conflicting legacy branch
protection rule over the same branch.

Set:

- **Name:** `Protect master`
- **Enforcement:** `Active`
- **Target:** default branch (`master`)
- **Bypass:** none for routine work. If an emergency owner bypass is retained, make it
  **For pull requests only**, require a written incident reason, and audit every use.
- **Restrict deletions:** on.
- **Block force pushes:** on.
- **Require a pull request before merging:** on.
  - Required approvals: `1` minimum.
  - Dismiss stale approvals when new commits are pushed: on.
  - Require review from Code Owners: on, but only after `CODEOWNERS` includes an appointed
    independent maintainer/team with write access.
  - Require approval of the most recent reviewable push or require approval from someone other
    than the last pusher: on. Prefer the stricter stale-review option where practical.
  - Require all conversations to be resolved: on.
  - Required merge type: `merge`, matching the repository's evidence-preserving merge-commit
    history. If the project intentionally switches to squash/rebase, change this setting and the
    documented release process together.
- **Require status checks:** on and strict (**Require branches to be up to date before merging**).
  Select GitHub Actions as the expected source and require these exact, recently observed checks:
  - `backend`
  - `runtime`
  - `frontend`
  - `e2e`
  - `dependency-review`
  - `docker`
  - `secrets`
  - `dependencies`
  - `repository-scan`
  - `policy`
- **Require code scanning results:** enable only after CodeQL default setup has completed a clean
  baseline. Require the CodeQL tool and block merge for every available `high`/`critical` security
  severity (and `error` analysis failures). Tighten the threshold after triaging the baseline.

Do not enable these without their prerequisite:

- **Require deployments:** off until a protected staging environment and real deployment check
  exist.
- **Require linear history:** off while merge commits are the chosen merge type.
- **Require signed commits:** recommended after every maintainer and automation/bot path has been
  tested with verified signatures; enabling it prematurely can strand valid dependency updates.
- **Merge queue:** optional for higher change volume; it does not replace strict required checks.

GitHub Free organization repositories receive rulesets when public. Rulesets can require reviews,
strict status checks from a selected app, conversation resolution, deletion/force-push protection,
and code-scanning results:

- <https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository>
- <https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets>

### Legacy branch-protection fallback

If a ruleset cannot be used, configure **Settings > Branches > Add branch protection rule** for
`master` with the equivalent PR review, CODEOWNERS, stale-review, conversation-resolution, strict
status-check, administrator-enforcement, force-push, and deletion settings above. Do not keep both
mechanisms active with different required checks or bypass policies.

## 4. Release-tag ruleset and immutable releases

Create a second active ruleset:

- **Name:** `Protect release tags`
- **Target tags:** `v*`
- **Restrict creation:** on; only the designated release maintainer(s) may bypass to create a tag.
- **Restrict updates:** on.
- **Restrict deletions:** on.
- **Block force pushes:** on.

Then enable **Settings > General > Releases > Enable release immutability** before the first
prerelease. It protects future published releases and their tags/assets; it does not retrofit an
existing release. The release workflow passes every asset directly to `gh release create`, whose
documented immutable-release flow creates a draft, uploads assets, then publishes it.

- <https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/establish-provenance-and-integrity/prevent-release-changes>
- <https://cli.github.com/manual/gh_release_create>

## 5. Private vulnerability reporting

After public visibility, open **Settings > Advanced Security** and enable **Private vulnerability
reporting**.

- [ ] Subscribe both owners and the security team to repository **Security alerts** and email
      notifications.
- [ ] From a non-admin account, verify that **Security > Advisories > Report a vulnerability** is
      visible and opens a private report—not a public issue.
- [ ] Keep `SECURITY.md` as the disclosure/SLA policy and ensure its fallback channel is monitored.
- [ ] Define who may triage, request a CVE, prepare a private fork, publish an advisory, and contact
      downstream users. Do not discuss an embargoed issue in a public issue or pull request.

Official configuration and notification steps:
<https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/configure-for-a-repository>

## 6. Code scanning

After public visibility, open **Settings > Advanced Security > CodeQL analysis > Set up > Default**.

- [ ] Select Python and JavaScript/TypeScript.
- [ ] Select the extended security query suite if the UI offers it.
- [ ] Enable CodeQL and wait for the initial analysis to finish successfully for both languages.
- [ ] Review tool status and file/language coverage; default setup being enabled is not proof that a
      successful scan ran.
- [ ] Fix or explicitly triage every alert. Treat a dismissed alert as a reviewed risk record with
      reason and reviewer, not as a way to make the count zero.
- [ ] After the clean baseline, add CodeQL to the `master` ruleset's required code-scanning results.
- [ ] Confirm scans occur on `master`, pull requests, and the scheduled cadence shown by GitHub.

GitHub recommends default setup first; public repositories with Actions enabled are eligible:
<https://docs.github.com/en/code-security/how-tos/find-and-fix-code-vulnerabilities/configure-code-scanning/configure-code-scanning>

## 7. Secret scanning and push protection

GitHub secret scanning runs automatically for public repositories and scans full Git history across
all branches. After changing visibility:

- [ ] Confirm **Settings > Advanced Security > Secret scanning** is active and let the initial
      full-history scan complete.
- [ ] Enable repository **Push protection**. It is a separate, default-off preventative control.
- [ ] Review every open and closed/bypassed alert. Immediately revoke/rotate any genuine secret;
      never close an alert merely because the text was removed.
- [ ] Subscribe owners/security maintainers to secret-scanning and bypass notifications.
- [ ] If available on the selected plan, enable validity checks and generic patterns. Add bounded
      custom patterns for MCPlica-specific credential formats only after dry-run review of false
      positives.
- [ ] If delegated bypass is available, allow a small security-review group to approve requests;
      do not broadly exempt all writers. Require an auditable reason and expiry for every bypass.
- [ ] Keep the repository's pinned Gitleaks and Trivy workflows required. GitHub scanning is an
      additional independent control, not a replacement.

- <https://docs.github.com/en/code-security/concepts/secret-security/secret-scanning>
- <https://docs.github.com/en/code-security/concepts/secret-security/push-protection>

## 8. Public repository and prerelease verification

- [ ] Add a concise repository description, homepage if one exists, and topics such as `mcp`,
      `openapi`, `fastapi`, `react`, and `self-hosted`.
- [ ] Verify the default branch is still `master`, clone/issue/security links point to
      `waqoor/MCPlica`, and badges/workflow identities resolve under the organization.
- [ ] Confirm Issues are intended to be public; keep security reports out of Issues. Decide
      explicitly whether Discussions, Wiki, Projects, Pages, and public forking should remain off.
- [ ] Enable **Automatically delete head branches** after pull requests if branch retention is not
      needed for evidence. Never delete the protected default or release tags.
- [ ] Review Actions permissions for fork pull requests and first-time contributors. Workflows that
      handle untrusted pull requests must not expose write tokens or secrets.
- [ ] Verify the release workflow can write contents, packages, attestations, and OIDC only for the
      tag job, and that the resulting GHCR packages link back to this repository.
- [ ] Publish the selected prerelease only from an annotated (preferably signed) tag that exactly
      matches `VERSION` and points to the reviewed `master` commit. Do not mark it Latest.
- [ ] Verify the Release is marked **Pre-release**, every expected asset exists, checksums and
      Cosign signatures verify, all three image tags resolve to recorded immutable digests, and
      provenance/SBOM attestations match the tag workflow identity.
- [ ] Keep production-host, real-provider, backup/restore, upgrade, rollback, DNS/TLS, and recovery
      gates open unless they were separately executed. A public prerelease is not production
      certification.

## Owner sign-off record

- Visibility-change time and actor:
- Final public `master` SHA:
- Ruleset URLs/export:
- CodeQL initial-run URL and alert disposition:
- Secret-scanning completion and alert disposition:
- Private vulnerability-reporting external test:
- Dependabot re-index result:
- Immutable-releases setting evidence:
- Prerelease tag and Release URL:
- GHCR package/digest/attestation evidence:
- Independent technical reviewer:
- Founder/release authorization:
- Residual risks, owner, and review date:
