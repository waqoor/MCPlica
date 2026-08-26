FROM ghcr.io/astral-sh/uv:0.12.1@sha256:cf4eedcaa81655197f625739489effcbe71b61ceb1506f332c3facae5deceded AS uv

FROM python:3.13.15-slim-trixie@sha256:7e3a6aca9d74f93cca21a91d86a8dad8c34749afd5b4a98ee481c9c47b9f5ed4
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/workspace/backend/.venv \
    PATH=/workspace/backend/.venv/bin:$PATH
COPY --from=uv /uv /uvx /bin/
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y --no-install-recommends \
    && DEBIAN_FRONTEND=noninteractive apt-get purge -y --allow-remove-essential \
        gzip perl-base \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /usr/local/lib/python3.13/ensurepip \
        /usr/local/lib/python3.13/site-packages/pip \
        /usr/local/lib/python3.13/site-packages/pip-26.2.1.dist-info \
        /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.13 \
    && useradd --create-home --uid 10001 mcplica \
    && mkdir -p /data/artifacts \
    && chown -R mcplica:mcplica /data/artifacts
WORKDIR /workspace
COPY pyproject.toml uv.lock ./
COPY packages/contracts /workspace/packages/contracts
COPY mcp_runtime/pyproject.toml /workspace/mcp_runtime/pyproject.toml
COPY backend /workspace/backend
COPY migrations /workspace/migrations
RUN uv sync --frozen --package mcplica-backend --no-dev --no-editable \
    && rm -rf /root/.cache/uv \
    && chown -R mcplica:mcplica /workspace/backend/.venv
WORKDIR /workspace/backend
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
