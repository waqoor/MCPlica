SHELL := /bin/bash
COMPOSE := docker compose --env-file .env -f infra/compose.yaml

.PHONY: install-python install-frontend lock backend-dev frontend-dev migrate test critical-coverage lint typecheck format api-contract api-contract-check compose-up compose-down compose-logs runtime-build validate

install-python:
	UV_PROJECT_ENVIRONMENT=backend/.venv uv sync --project backend
	UV_PROJECT_ENVIRONMENT=mcp_runtime/.venv uv sync --project mcp_runtime

install-frontend:
	cd frontend && corepack enable && pnpm install

lock:
	uv lock
	cd frontend && corepack enable && pnpm install --lockfile-only

backend-dev:
	cd backend && UV_PROJECT_ENVIRONMENT=.venv uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend-dev:
	cd frontend && corepack enable && pnpm dev

migrate:
	cd backend && UV_PROJECT_ENVIRONMENT=.venv uv run alembic -c ../migrations/alembic.ini upgrade head

test:
	cd backend && UV_PROJECT_ENVIRONMENT=.venv uv run pytest tests ../packages/contracts/tests
	cd mcp_runtime && UV_PROJECT_ENVIRONMENT=.venv uv run pytest
	cd frontend && corepack enable && pnpm test:run

critical-coverage:
	cd backend && UV_PROJECT_ENVIRONMENT=.venv uv run pytest -c pyproject.toml tests ../packages/contracts/tests --cov=app --cov-report=json:coverage-critical.json
	cd backend && UV_PROJECT_ENVIRONMENT=.venv uv run python scripts/check_critical_coverage.py coverage-critical.json

lint:
	cd backend && UV_PROJECT_ENVIRONMENT=.venv uv run ruff check app tests ../packages/contracts/src ../packages/contracts/tests
	cd mcp_runtime && UV_PROJECT_ENVIRONMENT=.venv uv run ruff check app tests
	cd frontend && corepack enable && pnpm lint

typecheck:
	cd backend && UV_PROJECT_ENVIRONMENT=.venv uv run pyright app ../packages/contracts/src
	cd mcp_runtime && UV_PROJECT_ENVIRONMENT=.venv uv run pyright app
	cd frontend && corepack enable && pnpm typecheck

format:
	cd backend && UV_PROJECT_ENVIRONMENT=.venv uv run ruff format app tests ../packages/contracts/src ../packages/contracts/tests
	cd mcp_runtime && UV_PROJECT_ENVIRONMENT=.venv uv run ruff format app tests
	cd frontend && corepack enable && pnpm format

api-contract:
	cd backend && UV_PROJECT_ENVIRONMENT=.venv uv run python generate_openapi.py
	cd frontend && corepack enable && pnpm generate:api

api-contract-check:
	cd backend && UV_PROJECT_ENVIRONMENT=.venv uv run python generate_openapi.py --check
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

.PHONY: init-env compose-check compose-test
init-env:
	python scripts/init_env.py

compose-check:
	$(COMPOSE) config --quiet

compose-test:
	PYTHONPATH=backend:tests/integration uv run --project backend --frozen --extra dev python tests/integration/full_stack_workflow.py --api-base http://127.0.0.1:8080/api/v1 --report output/compose-validation/workflow.json
