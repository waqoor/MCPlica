FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 mcplica && pip install --no-cache-dir uv
WORKDIR /workspace
COPY packages/contracts /workspace/packages/contracts
COPY mcp_runtime /workspace/mcp_runtime
WORKDIR /workspace/mcp_runtime
RUN uv pip install --system -e ../packages/contracts -e . && mkdir -p /runtime && chown -R mcplica:mcplica /runtime /workspace
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
