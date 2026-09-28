# Testing

MCPlica has four independently runnable test layers — backend (FastAPI app), MCP runtime (the
generic serving image), frontend (React), and cross-service integration/acceptance — plus
lint/typecheck/format gates on both Python and TypeScript. Everything is driven by pinned
`Makefile` targets so local runs match CI exactly. Most backend/runtime tests use mocks; a smaller,
explicitly marked set (`postgres_integration`, `docker_integration`) runs against real
infrastructure and is mandatory for changes that touch foundational data ownership or runtime
behavior — mock-only coverage is not accepted for those.

## Backend tests

```bash
make install-python   # uv sync, frozen, both backend and mcp_runtime
make lint             # ruff check: backend + mcp_runtime + frontend eslint
make typecheck        # pyright: backend + mcp_runtime, tsc for frontend
make format-check     # ruff format --check
make test             # backend pytest + mcp_runtime pytest + frontend vitest, all three
```

Backend pytest alone (mock-based tests only, `postgres_integration`/`docker_integration` excluded
by default since they're opt-in markers):

```bash
cd backend && uv run --frozen --extra dev pytest -c pyproject.toml tests ../packages/contracts/tests ../tests/integration/test_fixture_server.py
```

A scoped run during development — filter by filename or `-k <keyword>` to target just the module
you're changing; ruff (`E`, `F`, `I`, `UP`, `B`, `SIM` rule sets, 100-char line length) runs
separately and fast, so check it before every commit.

## MCP runtime tests

The generic MCP runtime image (`mcp_runtime/`) has its own dependency set and test suite, run in
isolation from the builder backend:

```bash
cd mcp_runtime
uv run pytest tests/test_manifest_security.py tests/test_protocol_and_auth.py
```

`test_manifest_security.py` and `test_protocol_and_auth.py` exercise exactly the two things a
deployed runtime must get right on its own, without the control plane: that a manifest can't be
abused to reach unintended hosts/operations, and that MCP protocol negotiation plus inbound auth
(bearer/OIDC) behave correctly. `make test` runs the full `mcp_runtime` suite as part of the
standard three-suite pass.

## Frontend tests

```bash
pnpm lint          # eslint
pnpm typecheck     # tsc -b (app) + tsconfig.e2e.json (e2e types)
pnpm test          # vitest, watch mode
pnpm test:run      # vitest, single run — use this one for CI-equivalent local checks
pnpm test:e2e      # Playwright end-to-end suite
```

Unit/component tests live alongside the code they cover (`*.test.tsx`, e.g. `dashboard.test.tsx`
next to `dashboard.tsx`). Playwright e2e runs against a real running stack and is hosted-only in
CI; its retries are treated as diagnostic, not a pass condition — a flaky retry still fails the
build rather than being silently accepted.

## Integration and acceptance tests

Three tiers above unit tests, from narrowest to broadest:

- **Focused regressions** — targeted files like `test_compose_configuration.py` and
  `test_fixture_server.py`, run with plain `pytest`, no special infrastructure.
- **`postgres_integration` marker** — opt-in, uses real transactions against a disposable
  PostgreSQL database. **Mandatory for any change to foundational data ownership** (current-source
  selection, concurrent observation ordering, dead-owner cancellation recovery, stale-build
  rejection, deployment state-machine ordering, migration rehearsal). Mock-only coverage is
  explicitly not accepted here — this is how a real schema/constraint bug (like MCP-011's
  JSONB-null issue) gets caught before production. Needs `TEST_DATABASE_URL` set to a real
  Postgres instance.
- **`docker_integration` / full clean-install acceptance** — the broadest tier: a fresh clone on a
  **disposable Linux Docker host**, no existing environment file or volumes. It changes model
  settings, creates real projects/secrets, stops services, replaces runtimes. Requires
  `RUN_DOCKER_INTEGRATION=1` and refuses `ENV=production` outright — this is a verification
  operation, never something run against a live deployment.

```bash
uv sync --project backend --frozen --extra dev
python tests/integration/prepare_compose.py
```

## What CI runs

Five jobs in `.github/workflows/ci.yml`:

- **backend** — runs against a real `postgres:18.6` service container (not a mock), so
  `postgres_integration`-marked tests execute for real in CI even though they self-skip locally
  without `TEST_DATABASE_URL` set. Also: ruff lint + format check, pyright, Alembic migration
  upgrade/check, OpenAPI contract-drift check, pytest with coverage, and a
  `check_critical_coverage.py` gate that fails the build if critical modules fall under their
  required coverage threshold. Plus repo hygiene: release-version check, docs validation,
  tracked-source checksum manifest verification.
- **runtime** — the same lint/format/typecheck/test cycle for `mcp_runtime` in isolation.
- **frontend** — eslint, typecheck, vitest, and (implied by the Makefile) API contract drift check
  against the generated OpenAPI types.
- **dependency-review** — flags newly introduced vulnerable dependencies on a PR.
- **docker** — image build verification.

Nothing here is optional-on-merge: all five are required checks. There is no separate "nightly" or
"best-effort" test tier — what runs on every push is the full bar.

## Known coverage gaps

- **MCP-002 has no dedicated regression test** (see [known issues](known-issues.md)) — the fix is
  real and lint-clean, but nothing in the suite would catch a future regression of it.
- **`test_source_snapshot_checksum_manifest_*` needs a real `git` binary on PATH** (it shells out
  to `git cat-file`). A minimal Python container without git installed will fail these two tests
  even when the code under test is completely unrelated — worth knowing so a red result here isn't
  mistaken for a real regression when testing outside the pinned CI image.
- **`postgres_integration` tests require a real database connection to actually run** — skipped
  silently, not failed, when `TEST_DATABASE_URL` is unset. It's easy to believe you've verified a
  foundational data-ownership change when you've actually just skipped the one suite that proves
  it.
