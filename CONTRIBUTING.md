# Contributing to MCPlica

Thank you for contributing.

## Contributor License Agreement

MCPlica uses a **CLA-only** contribution model for external code contributions. **DCO is not used.** External code contributions may not be merged until the contributor's applicable individual/entity CLA status is verified. Repository owners, organization members, explicitly authorized collaborators, and Dependabot are trusted repository actors and do not require an external CLA-service result.

The repository-level automation in `.github/workflows/cla.yml` first validates trusted repository actors from GitHub's pull-request metadata. For any other contributor, it reads the exact status/check name configured in the `CLA_STATUS_CONTEXT` repository variable. It succeeds only when the founder-approved CLA service reports success for the pull request head commit, reports an ordinary policy failure for unsigned contributions, and reports service unavailability separately. Maintainers must not bypass that external-contributor check or treat DCO sign-off as a substitute.

All contributors must follow `CODE_OF_CONDUCT.md`. Security vulnerabilities belong in private vulnerability reporting, not normal issues or pull requests.

## Engineering requirements

- Follow the architecture and design specifications in `docs/`.
- Do not add SaaS billing, tenant abstractions, chat/agent runtime, or HITL policy engines.
- Keep OpenRouter and Milvus out of the MCP serving runtime.
- Infrastructure integrations belong behind clients.
- Preserve deterministic executable API mappings.
- Add/adjust tests for every behavior change.
- Never commit secrets or user API documentation/specifications to fixtures without explicit redistribution rights.
- Keep generated executable behavior traceable to source evidence; mocks belong only in tests.
- Preserve API client/service boundaries and the monorepo's modular sub-services.

## Development setup

Use Python 3.13, uv, Node.js from `.node-version`, pnpm through Corepack, and Docker Compose v2. Copy `.env.example` to `.env`, replace every blank or `REPLACE_...` value, then run:

```bash
make install-python
make install-frontend
make migrate
```

See `docs/operations/installation.md` and `docs/operations/configuration.md` for host-specific and production requirements.

## Pull requests

1. Create a focused `feature/<topic>`, `fix/<topic>`, `docs/<topic>`, or
   `release/vX.Y.Z-preparation` branch. Release tags are `vX.Y.Z` or `vX.Y.Z-prerelease`; do not
   use a tag as a development branch.
2. Add behavior-focused tests and any required migration or contract fixture.
3. Run `make repository-check`, `make format-check`, `make lint`, `make typecheck`,
   `make api-contract-check`, and `make test`.
4. For frontend changes, run `pnpm --dir frontend test`, `pnpm --dir frontend build`, and the relevant `pnpm --dir frontend test:e2e` journeys.
5. Update user, operator, security, and release documentation affected by the change.
6. Explain architecture, security, data, compatibility, and rollback impact in the pull request.
7. Ensure contributor authorization passes before merge: trusted repository actors are recognized automatically, while external contributors require successful CLA verification.

## Versions and changelog

Root `VERSION` is the only version authority. For a release bump, edit that file, run
`python scripts/release_version.py --sync`, regenerate contracts, and review every resulting
change. Never edit only one package/runtime/image version. Internal protocol/schema/prompt
identifiers change only when their own contract changes.

Add user-visible, security, compatibility, migration, deprecation, and operator-impacting changes
under `CHANGELOG.md`'s `[Unreleased]` section. During release preparation, move those entries into
a dated version section and create `docs/releases/vX.Y.Z.md`. Fix-only commits may omit a changelog
entry only when they have no user, operator, security, compatibility, or release impact; explain
that decision in the pull request.

Commits should be reviewable and must not mix broad cleanup with a functional change. A maintainer may request a design discussion before accepting changes to contracts, persistence, compiler behavior, runtime isolation, authentication, deployment, or governance.
