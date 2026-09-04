# Governance

MCPlica uses founder-led governance. Sponsorship, CLA acceptance, contribution volume, or company affiliation does not grant governance authority.

Roles progress from contributor to reviewer/maintainer only through sustained technical trust and explicit appointment. The founder retains final authority over architecture, project scope, releases, security policy, maintainer appointments/removal, licensing direction, and branding, subject to rights already granted under applicable open-source licenses and contributor agreements.

## Roles and decisions

- Contributors propose changes and participate in review after accepting the contribution and conduct policies.
- Reviewers may review within explicitly delegated areas but cannot merge, release, appoint maintainers, or change policy unless separately authorized.
- Maintainers listed in `MAINTAINERS.md` may merge and operate releases within their assigned responsibility.
- The founder resolves disputes and makes final decisions on cross-cutting architecture, scope, security disclosure, release acceptance, governance, licensing direction, and trademarks.

## Current single-maintainer operation

MCPlica currently has one organization owner and one maintainer, `@yazeedhasan97`. Until another
eligible maintainer is explicitly appointed, the founder may author and merge a change after every
required automated check passes on the exact pull-request head and all review conversations are
resolved. The pull request or release record must state that this is an owner-authorized
single-maintainer merge; it must not describe the decision as independent review.

This operating model does not waive a failed deterministic, authentication, secret, migration,
image-integrity, dependency, or runtime-health gate. It also leaves an acknowledged continuity and
review-independence risk. When an eligible independent maintainer is appointed, protected or
release-boundary changes should require that maintainer's approval unless a documented emergency
process applies.

Routine changes are decided through pull-request review against the authoritative documents and passing required checks. Material changes to contracts, security boundaries, persistence, deployment, governance, or licensing require an explicit written decision and migration/rollback analysis. Security incidents may be handled privately until coordinated disclosure.

Releases follow Semantic Versioning and the repository release process. The founder or an
explicitly delegated maintainer confirms the checklist, but cannot waive a failed deterministic,
authentication, secret, migration, image-integrity, or runtime-health gate. Published tags and
image tags are immutable; corrections use a new version.

Maintainers must disclose conflicts, recuse themselves when impartial review is not possible, protect embargoed reports and contributor data, and never trade approval for sponsorship or commercial benefit. Appointment and removal are recorded by pull request. Inactivity alone is not misconduct, but access may be removed to reduce security risk.

If the founder becomes unavailable, existing maintainers may keep security fixes and existing release lines operating. A permanent succession decision must be recorded publicly, preserve already granted license rights, and maintain the stated project boundaries unless governance is formally amended.

See `docs/open_source_and_sponsorship_model.md` for the authoritative model.
