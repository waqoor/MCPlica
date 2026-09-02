SHELL := /bin/bash
ENV_FILE ?= .env
BACKEND_ENV := $(CURDIR)/backend/.venv
RUNTIME_ENV := $(CURDIR)/mcp_runtime/.venv
COMPOSE := MCPLICA_ENV_FILE="$(abspath $(ENV_FILE))" docker compose --env-file "$(ENV_FILE)" -f infra/compose.yaml

.PHONY: install-python install-frontend lock backend-dev frontend-dev migrate test critical-coverage lint typecheck format api-contract api-contract-check compose-up compose-down compose-logs runtime-build validate manifest manifest-check

install-python:
	UV_PROJECT_ENVIRONMENT="$(BACKEND_ENV)" uv sync --project backend --frozen --extra dev
	UV_PROJECT_ENVIRONMENT="$(RUNTIME_ENV)" uv sync --project mcp_runtime --frozen --extra dev

install-frontend:
	cd frontend && corepack enable && pnpm install --frozen-lockfile

lock:
	uv lock
	cd frontend && corepack enable && pnpm install --lockfile-only

backend-dev:
	cd backend && UV_PROJECT_ENVIRONMENT="$(BACKEND_ENV)" uv run --frozen --extra dev uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend-dev:
	cd frontend && corepack enable && pnpm dev

migrate:
	cd backend && UV_PROJECT_ENVIRONMENT="$(BACKEND_ENV)" uv run --frozen --extra dev alembic -c ../migrations/alembic.ini upgrade head

test:
	cd backend && UV_PROJECT_ENVIRONMENT="$(BACKEND_ENV)" uv run --frozen --extra dev pytest tests ../packages/contracts/tests ../tests/integration/test_fixture_server.py
	cd mcp_runtime && UV_PROJECT_ENVIRONMENT="$(RUNTIME_ENV)" uv run --frozen --extra dev pytest
	cd frontend && corepack enable && pnpm test:run

critical-coverage:
	cd backend && UV_PROJECT_ENVIRONMENT="$(BACKEND_ENV)" uv run --frozen --extra dev pytest -c pyproject.toml tests ../packages/contracts/tests --cov=app --cov-report=json:coverage-critical.json
	cd backend && UV_PROJECT_ENVIRONMENT="$(BACKEND_ENV)" uv run --frozen --extra dev python scripts/check_critical_coverage.py coverage-critical.json

lint:
	cd backend && UV_PROJECT_ENVIRONMENT="$(BACKEND_ENV)" uv run --frozen --extra dev ruff check app tests ../packages/contracts/src ../packages/contracts/tests
	cd mcp_runtime && UV_PROJECT_ENVIRONMENT="$(RUNTIME_ENV)" uv run --frozen --extra dev ruff check app tests
	cd frontend && corepack enable && pnpm lint

typecheck:
	cd backend && UV_PROJECT_ENVIRONMENT="$(BACKEND_ENV)" uv run --frozen --extra dev pyright app ../packages/contracts/src
	cd mcp_runtime && UV_PROJECT_ENVIRONMENT="$(RUNTIME_ENV)" uv run --frozen --extra dev pyright app
	cd frontend && corepack enable && pnpm typecheck

format:
	cd backend && UV_PROJECT_ENVIRONMENT="$(BACKEND_ENV)" uv run --frozen --extra dev ruff format app tests ../packages/contracts/src ../packages/contracts/tests
	cd mcp_runtime && UV_PROJECT_ENVIRONMENT="$(RUNTIME_ENV)" uv run --frozen --extra dev ruff format app tests
	cd frontend && corepack enable && pnpm format

api-contract:
	cd backend && UV_PROJECT_ENVIRONMENT="$(BACKEND_ENV)" uv run --frozen --extra dev python generate_openapi.py
	cd frontend && corepack enable && pnpm generate:api

api-contract-check:
	cd backend && UV_PROJECT_ENVIRONMENT="$(BACKEND_ENV)" uv run --frozen --extra dev python generate_openapi.py --check
	cd frontend && corepack enable && pnpm check:api

compose-up:
	$(COMPOSE) up --build -d --wait --wait-timeout 300
	$(COMPOSE) exec -T api python -m app.cli.ensure_development_admin

compose-down:
	$(COMPOSE) down

compose-logs:
	$(COMPOSE) logs -f

runtime-build:
	$(COMPOSE) build runtime-validator

validate:
	python scripts/validate_starter.py

manifest:
	python scripts/checksum_manifest.py --write

manifest-check:
	python scripts/checksum_manifest.py --check

.PHONY: init-env compose-check compose-test
init-env:
	python scripts/init_env.py

compose-check:
	$(COMPOSE) config --quiet

compose-test:
	RUN_DOCKER_INTEGRATION=1 PYTHONPATH=backend:tests/integration uv run --project backend --frozen --extra dev python tests/integration/full_stack_workflow.py --api-base http://127.0.0.1:8080/api/v1 --report output/compose-validation/workflow.json
