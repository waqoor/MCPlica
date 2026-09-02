ARG PYTHON_BASE="python:3.13.15-slim-trixie@sha256:7e3a6aca9d74f93cca21a91d86a8dad8c34749afd5b4a98ee481c9c47b9f5ed4"

FROM ${PYTHON_BASE} AS builder
ENV UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv
COPY --from=ghcr.io/astral-sh/uv:0.12.9@sha256:8b940d3a9d65bed080436972241af2e21c84b5e8c9193f7014ed71479ee795ff /uv /uvx /bin/
WORKDIR /workspace
COPY pyproject.toml uv.lock ./
COPY backend/pyproject.toml /workspace/backend/pyproject.toml
COPY packages/contracts /workspace/packages/contracts
COPY mcp_runtime /workspace/mcp_runtime
RUN uv sync --frozen --package mcplica-runtime --no-dev --no-editable

FROM ${PYTHON_BASE} AS runtime
ARG VERSION
ARG VCS_REF=local
ARG SOURCE_URL=https://github.com/yazeedhasan97/MCPlica
LABEL org.opencontainers.image.title="MCPlica generic MCP runtime" \
      org.opencontainers.image.description="Manifest-driven MCP Streamable HTTP runtime" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.licenses="AGPL-3.0-only" \
      org.opencontainers.image.source="${SOURCE_URL}"
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH \
    MCP_RUNTIME_VERSION=${VERSION}
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y --no-install-recommends \
    && DEBIAN_FRONTEND=noninteractive apt-get purge -y --allow-remove-essential \
        gzip perl-base \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /usr/local/lib/python3.13/ensurepip \
        /usr/local/lib/python3.13/site-packages/pip \
        /usr/local/lib/python3.13/site-packages/pip-26.2.1.dist-info \
        /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.13 \
    && groupadd --gid 10001 mcplica \
    && useradd --uid 10001 --gid 10001 --no-create-home \
        --home-dir /nonexistent --shell /usr/sbin/nologin mcplica \
    && mkdir -p /runtime /run/secrets \
    && chown 10001:10001 /runtime /run/secrets
COPY VERSION /opt/mcplica/VERSION
RUN test -n "${VERSION}" && test "$(cat /opt/mcplica/VERSION)" = "${VERSION}"
COPY --from=builder --chown=10001:10001 /opt/venv /opt/venv
USER 10001:10001
WORKDIR /
EXPOSE 8000
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=6 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=2).read()"]
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-server-header"]
