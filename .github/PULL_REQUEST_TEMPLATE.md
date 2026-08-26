## Outcome

Describe the user-visible or operational result and link the issue/design decision.

## Contract and architecture impact

Identify affected API/domain contracts, migrations, generated artifacts, security boundaries, and rollback behavior. State “none” where applicable.

## Evidence

List the exact commands and behavior/E2E scenarios run. Include sanitized screenshots only when they prove functional behavior.

## Review checklist

- [ ] The change stays within MCPlica's documented scope and uses the canonical implementation path.
- [ ] API/domain contracts remain typed; components do not make ad hoc backend/external requests.
- [ ] State-changing browser requests retain cookie, CSRF, authorization, and secret-handling safeguards.
- [ ] Tests cover changed behavior without adding fixture-only production logic.
- [ ] `make lint`, `make typecheck`, and `make test` pass for affected workspaces.
- [ ] Frontend changes pass `pnpm test`, `pnpm build`, and relevant Playwright journeys.
- [ ] Migrations, documentation, operations, and rollback instructions are updated where applicable.
- [ ] No credentials, private specifications, generated secret material, or sensitive logs are included.
- [ ] External contributors have verified CLA status; DCO sign-off is not requested.
