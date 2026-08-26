SHELL := /bin/bash
COMPOSE := docker compose --env-file .env -f infra/compose.yaml

.PHONY: install-python install-frontend lock backend-dev frontend-dev migrate test lint typecheck format compose-up compose-down compose-logs runtime-build validate

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
	cd backend && UV_PROJECT_ENVIRONMENT=.venv uv run pytest
	cd mcp_runtime && UV_PROJECT_ENVIRONMENT=.venv uv run pytest

lint:
	cd backend && UV_PROJECT_ENVIRONMENT=.venv uv run ruff check app tests
	cd mcp_runtime && UV_PROJECT_ENVIRONMENT=.venv uv run ruff check app tests
	cd frontend && corepack enable && pnpm lint

typecheck:
	cd backend && UV_PROJECT_ENVIRONMENT=.venv uv run pyright app
	cd mcp_runtime && UV_PROJECT_ENVIRONMENT=.venv uv run pyright app
	cd frontend && corepack enable && pnpm typecheck

format:
	cd backend && UV_PROJECT_ENVIRONMENT=.venv uv run ruff format app tests
	cd mcp_runtime && UV_PROJECT_ENVIRONMENT=.venv uv run ruff format app tests
	cd frontend && corepack enable && pnpm format

compose-up:
	$(COMPOSE) up --build -d

compose-down:
	$(COMPOSE) down

compose-logs:
	$(COMPOSE) logs -f

runtime-build:
	docker build -f infra/docker/runtime.Dockerfile -t mcplica/mcp-runtime:dev .

validate:
	python scripts/validate_starter.py
