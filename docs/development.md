# Development without the full Compose stack

The Make targets use the same absolute backend and runtime virtual-environment paths for
installation and execution, with frozen dependency resolution.

Install development dependencies with `make install-python` and `make install-frontend`. A
host-side backend also needs explicitly configured, secured, host-reachable PostgreSQL, Redis, and
Milvus endpoints; the base Compose file deliberately does not publish those services.

```bash
make backend-dev
make frontend-dev
```

The generic runtime is launched through the deployment worker so it receives a verified manifest
digest and a project-scoped, read-only secret bundle. Exercise it in isolation through its
security and protocol tests:

```bash
cd mcp_runtime
uv run pytest tests/test_manifest_security.py tests/test_protocol_and_auth.py
```

Deployed runtime liveness is `/healthz`, readiness is `/readyz`, and MCP Streamable HTTP is `/mcp`.
Do not inject ad hoc credential environment variables in place of the canonical secret bundle.

Use the complete [installation guide](operations/installation.md) for the canonical Compose stack,
and [tests/integration/README.md](../tests/integration/README.md) for full-stack acceptance.
